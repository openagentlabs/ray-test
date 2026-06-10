import {
  CloudWatchLogsClient,
  CreateLogStreamCommand,
  InvalidSequenceTokenException,
  PutLogEventsCommand,
  ResourceAlreadyExistsException,
  ResourceNotFoundException,
} from "@aws-sdk/client-cloudwatch-logs";
import { ExportResultCode, type ExportResult } from "@opentelemetry/core";
import type { LogRecordExporter } from "@opentelemetry/sdk-logs";
import type { ReadableLogRecord } from "@opentelemetry/sdk-logs";

import { readableLogRecordToJson } from "@/lib/logging/readable-log-json";

export interface CloudWatchLogExporterOptions {
  readonly region: string;
  readonly logGroupName: string;
  readonly logStreamName: string;
  /** Stable workload id (Terraform `service.id` tag). */
  readonly serviceId: string;
  /** OpenTelemetry `service.name`. */
  readonly serviceName: string;
  /** OpenTelemetry `service.instance.id`. */
  readonly serviceInstanceId: string;
}

const MAX_EVENTS_PER_BATCH = 500;

/**
 * Async {@link LogRecordExporter} that ships OpenTelemetry log records to Amazon CloudWatch Logs
 * using the AWS SDK v3 client (non-blocking `export` delegates to a background promise).
 */
export class CloudWatchLogRecordExporter implements LogRecordExporter {
  private readonly client: CloudWatchLogsClient;
  private readonly logGroupName: string;
  private readonly logStreamName: string;
  private readonly serviceId: string;
  private readonly serviceName: string;
  private readonly serviceInstanceId: string;
  private sequenceToken: string | undefined;
  private shutdownOnce = false;
  private ensuredStream = false;

  public constructor(options: CloudWatchLogExporterOptions) {
    this.client = new CloudWatchLogsClient({ region: options.region });
    this.logGroupName = options.logGroupName;
    this.logStreamName = options.logStreamName;
    this.serviceId = options.serviceId;
    this.serviceName = options.serviceName;
    this.serviceInstanceId = options.serviceInstanceId;
  }

  public export(
    logs: ReadableLogRecord[],
    resultCallback: (result: ExportResult) => void,
  ): void {
    if (this.shutdownOnce || logs.length === 0) {
      resultCallback({ code: ExportResultCode.SUCCESS });
      return;
    }

    void this.exportAsync(logs)
      .then(() => {
        resultCallback({ code: ExportResultCode.SUCCESS });
      })
      .catch(() => {
        // Never fail the OTel pipeline when CloudWatch is down (app must keep running).
        resultCallback({ code: ExportResultCode.SUCCESS });
      });
  }

  public async shutdown(): Promise<void> {
    this.shutdownOnce = true;
    this.client.destroy();
  }

  public async forceFlush(): Promise<void> {
    // Batching handled by BatchLogRecordProcessor; exporter is stateless aside from sequence token.
  }

  private async exportAsync(logs: ReadableLogRecord[]): Promise<void> {
    try {
      if (!this.ensuredStream) {
        await this.ensureLogInfrastructure();
        this.ensuredStream = true;
      }

      for (let i = 0; i < logs.length; i += MAX_EVENTS_PER_BATCH) {
        const slice = logs.slice(i, i + MAX_EVENTS_PER_BATCH);
        await this.putSlice(slice);
      }
    } catch {
      /* drop batch — CloudWatch must not break the application */
    }
  }

  private async ensureLogInfrastructure(): Promise<void> {
    try {
      await this.client.send(
        new CreateLogStreamCommand({
          logGroupName: this.logGroupName,
          logStreamName: this.logStreamName,
        }),
      );
    } catch (error: unknown) {
      if (!(error instanceof ResourceAlreadyExistsException)) {
        throw error;
      }
    }
  }

  private async putSlice(slice: ReadableLogRecord[]): Promise<void> {
    const events = slice.map((record, index) => ({
      message: JSON.stringify({
        service: {
          id: this.serviceId,
          name: this.serviceName,
          instanceId: this.serviceInstanceId,
        },
        ...readableLogRecordToJson(record),
      }),
      timestamp: Date.now() + index,
    }));

    await this.putWithRetry(events);
  }

  private async putWithRetry(
    events: readonly { message: string; timestamp: number }[],
  ): Promise<void> {
    try {
      const response = await this.client.send(
        new PutLogEventsCommand({
          logGroupName: this.logGroupName,
          logStreamName: this.logStreamName,
          logEvents: [...events],
          sequenceToken: this.sequenceToken,
        }),
      );
      this.sequenceToken = response.nextSequenceToken;
    } catch (error: unknown) {
      if (error instanceof InvalidSequenceTokenException) {
        this.sequenceToken = error.expectedSequenceToken;
        const response = await this.client.send(
          new PutLogEventsCommand({
            logGroupName: this.logGroupName,
            logStreamName: this.logStreamName,
            logEvents: [...events],
            sequenceToken: this.sequenceToken,
          }),
        );
        this.sequenceToken = response.nextSequenceToken;
        return;
      }

      if (error instanceof ResourceNotFoundException) {
        this.ensuredStream = false;
        await this.ensureLogInfrastructure();
        this.ensuredStream = true;
        await this.putWithRetry(events);
        return;
      }

      throw error;
    }
  }
}
