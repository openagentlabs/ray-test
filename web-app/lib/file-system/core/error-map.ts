import { ErrorCodes, appError, type AppError } from "./errors";

export function ioError(
  operation: string,
  path: string,
  detail: string,
): AppError {
  return appError(
    ErrorCodes.IO,
    `Could not ${operation} '${path}'.`,
    detail,
  );
}

export function mapNodeError(
  error: NodeJS.ErrnoException,
  operation: string,
  path: string,
): AppError {
  switch (error.code) {
    case "ENOENT":
      return appError(
        ErrorCodes.NOT_FOUND,
        `Path not found: '${path}'.`,
        error.message,
      );
    case "EACCES":
    case "EPERM":
      return appError(
        ErrorCodes.PERMISSION,
        `Permission denied for '${path}'.`,
        error.message,
      );
    case "EISDIR":
      return appError(
        ErrorCodes.VALIDATION,
        `Expected a file but found a directory: '${path}'.`,
        error.message,
      );
    case "ENOSPC":
    case "EDQUOT":
      return ioError(operation, path, error.message);
    case "EIO":
    case "ESTALE":
    case "ETIMEDOUT":
    case "ENOTCONN":
    case "ESHUTDOWN":
      return ioError(operation, path, error.message);
    default:
      throw error;
  }
}
