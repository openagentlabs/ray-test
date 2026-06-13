###############################################################################
# infra/tf_lib/s3_shared_files — S3 Inventory (opt-in via var.inventory)
###############################################################################

resource "aws_s3_bucket_inventory" "this" {
  count = var.inventory == null ? 0 : 1

  bucket = aws_s3_bucket.this.id
  name   = var.inventory.id

  included_object_versions = var.inventory.included_object_versions

  schedule {
    frequency = var.inventory.schedule_frequency
  }

  destination {
    bucket {
      bucket_arn = var.inventory.destination_bucket_arn
      prefix     = var.inventory.destination_prefix
      format     = var.inventory.destination_format
    }
  }

  dynamic "filter" {
    for_each = var.inventory.filter_prefix == null ? [] : [var.inventory.filter_prefix]
    content {
      prefix = filter.value
    }
  }

  optional_fields = var.inventory.optional_fields
}
