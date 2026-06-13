# Local EC2 pip wheelhouse test

Mirrors the Jenkins stage **EC2 MT Test - Build and Install Offline Bundle** pip download (same `requirements-ec2-wheelhouse.txt` and manylinux cp310 flags). Does **not** upload to S3.

## Run

From repo root:

```bash
chmod +x test/ec2-pip-wheelhouse-local/run-download.sh
./test/ec2-pip-wheelhouse-local/run-download.sh
```

Wheels are written to `test/ec2-pip-wheelhouse-local/wheels/`.

## Remove

```bash
rm -rf test/ec2-pip-wheelhouse-local/wheels
# or delete this entire folder
```
