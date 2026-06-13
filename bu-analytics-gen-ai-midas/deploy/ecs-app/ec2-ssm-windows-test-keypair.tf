locals {
  ec2_ssm_windows_test_key_pair_effective = var.ec2_ssm_windows_test_enabled && var.ec2_ssm_windows_test_key_pair_enabled
  # Pubkey material only when the key pair is enabled (avoids reading the file when disabled).
  ec2_ssm_windows_test_key_pub_material = local.ec2_ssm_windows_test_key_pair_effective ? trimspace(file("${path.root}/../../keypair/midas-windows-dev-local.pem.pub")) : ""
  # Stable short suffix from key material so a pubkey rotation uses a new EC2 key name. That avoids
  # ImportKeyPair InvalidKeyPair.Duplicate when Terraform would otherwise create the replacement before the old same-name pair is gone.
  ec2_ssm_windows_test_key_name_suffix = local.ec2_ssm_windows_test_key_pair_effective ? substr(sha256(local.ec2_ssm_windows_test_key_pub_material), 0, 8) : ""
}

# Public key lives in repo (keypair/midas-windows-dev-local.pem.pub). Private midas-windows-dev-local.pem
# stays local only (gitignored); operators use it for EC2 GetPasswordData / Windows admin password decrypt.
resource "aws_key_pair" "ec2_ssm_windows_test" {
  count = local.ec2_ssm_windows_test_key_pair_effective ? 1 : 0

  key_name   = "midas-${var.environment}-ec2-ssm-windows-test-${local.ec2_ssm_windows_test_key_name_suffix}"
  public_key = local.ec2_ssm_windows_test_key_pub_material

  tags = {
    Name        = "midas-${var.environment}-ec2-ssm-windows-test-${local.ec2_ssm_windows_test_key_name_suffix}"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "ec2-ssm-windows-test-keypair"
  }

  lifecycle {
    create_before_destroy = false
  }
}
