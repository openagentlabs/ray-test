# tf — command reference (on demand)

> **Read policy:** Open **only** when **workflow.md** **RUN** cites a section below, or **ON_ERROR** needs the [error map](#common-error--jmp-map). Read **one section at a time**; do not load the whole file preemptively.

**Setup** (read once per session when first **RUN**):

```bash
export TF_ROOT="infra/aws/aws_tf"
export AWS_CLI_PROFILE="kt-acc"          # constants.mdc
export AWS_DEFAULT_REGION="us-east-1"
export AWS_OUTPUT_FORMAT="json"
cd "$TF_ROOT"
```

---

## Pre-flight (AWS identity)

Before **apply**, **destroy**, or first AWS action this session:

```bash
aws sts get-caller-identity \
  --profile "$AWS_CLI_PROFILE" \
  --region "$AWS_DEFAULT_REGION" \
  --output "$AWS_OUTPUT_FORMAT"
```

**Pass:** exit 0; `Account` = **`AWS_ACCOUNT_ID`** from **constants.mdc**. **Fail:** stop → **`Jmp: WorkflowPreflight`** after user fixes creds.

---

## init

```bash
terraform init
terraform init -upgrade      # user request only
terraform init -reconfigure    # backend block changed
```

---

## fmt

```bash
terraform fmt -recursive
terraform fmt -check -recursive   # CI, no write
```

---

## validate

```bash
terraform validate
```

---

## plan

```bash
terraform plan -out=tfplan
terraform plan -refresh=false -out=tfplan   # debug only; note in handoff
terraform plan -target=module.<module_label> -out=tfplan
terraform show tfplan
```

Lock error → **`Delay: 10s`**, **`Jmp: WorkflowPlan`** (max 3).

---

## apply

Same-turn user approval required.

```bash
terraform apply tfplan              # preferred
terraform apply                     # user prefers interactive
terraform apply -auto-approve       # user said deploy + non-interactive
```

Prefer **`tfplan`** over bare **`-auto-approve`**.

---

## destroy

Same gate as apply.

```bash
terraform plan -destroy -out=tfdestroy
terraform apply tfdestroy
terraform destroy -target=module.<module_label>   # explicit name required
```

---

## output

```bash
terraform output
terraform output -json
terraform output <output_name>
```

---

## state (inspect / troubleshoot)

```bash
terraform state list
terraform state show '<address>'
terraform state mv '<from>' '<to>'
terraform state rm '<address>'      # expert only
terraform state taint '<address>'
```

Plan immediately after **`state mv`**.

---

## checkov

```bash
checkov -d infra/aws/aws_tf --compact --quiet
checkov -d infra/aws/aws_tf/modules/<name> --compact
checkov -d infra/aws/aws_tf -o json
```

Traffic-light report per **`.cursor/rules/tools/checkov-tool.mdc`**.

---

## tflint (optional)

```bash
tflint --init
tflint
```

---

## providers

```bash
terraform providers
```

---

## Common error → Jmp map

| Error | Fix | Jump |
|-------|-----|------|
| Not initialized | init | **`Jmp: WorkflowInit:`** |
| Invalid syntax | Edit HCL, fmt | **`Jmp: WorkflowFmt:`** |
| State lock | Wait, retry | **`Delay: 10s`**, **`Jmp: WorkflowPlan:`** or **`WorkflowApply:`** |
| Wrong AWS account | Stop | User fix → **`Jmp: WorkflowPreflight:`** |
| Provider drift | `init -upgrade` (consent) | **`Jmp: WorkflowInit:`** |
| Checkov critical | Fix HCL or user accepts risk | **`Jmp: WorkflowHandoff:`** |

Workflow stages and extensions: **[workflow.md](workflow.md)** — not this file.
