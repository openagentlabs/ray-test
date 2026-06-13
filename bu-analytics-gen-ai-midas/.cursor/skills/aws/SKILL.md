---
name: aws-tool-acm-certs
description: >-
  Guides beginners through MIDAS ACM TLS for AWS Application Load Balancer (ALB) HTTPS
  listeners and web applications: .cursor/scripts/aww-cert-generate-injector.py
  generates self-signed PEM certs (ALB/ACM-shaped), imports to ACM, lists/deletes ACM
  certs by index (temp JSON cache). Triggers: ALB TLS, HTTPS web app hostname, ACM cert,
  aww-cert-generate-injector, @aws_tool. If the user does not state which function to run,
  ask A/B/C/D first, then one flag question at a time (presets + custom), then run from repo root.
---

# aws_tool — ACM certificate helper (`aww-cert-generate-injector.py`)

## Scope — **AWS ALB** and **web applications (HTTPS)**

Treat this skill and script as focused on **TLS for AWS Application Load Balancers** and **HTTPS web workloads**:

| Use case | How this tool fits |
|----------|---------------------|
| **ALB HTTPS listener** | Certs are created/imported into **ACM in the same AWS region as the ALB**, then attached to the listener. The script’s generate path targets **server TLS** (RSA, SAN DNS = hostname clients use in the URL / SNI). |
| **Web applications** | Primary name (`--domain` / `--prompt-domain`) should be the **public or internal HTTPS hostname** users or APIs call (e.g. `app.example.com`). Extra names → `--san`. |

**Out of scope unless the user explicitly asks:** non-HTTPS protocols, generic “any X.509” stories with no ALB/web angle, mTLS policy design, or non-ACM certificate stores. If the user drifts there, answer briefly and steer back to **ALB + ACM + HTTPS hostname**, or flag that a different AWS pattern applies.

## Canonical script (always use this path)

Run from the **MIDAS repository root** (`bu-analytics-gen-ai-midas`):

```bash
python3 .cursor/scripts/aww-cert-generate-injector.py [FLAGS]
```

- **Never** assume a different filename unless the user explicitly renamed the script.
- For the full flag list and long examples, the agent may run once (read-only check):

  ```bash
  python3 .cursor/scripts/aww-cert-generate-injector.py --help
  ```

## Invocation summary table (**mandatory** whenever the agent runs the script)

Immediately **before** (in the same chat reply as) invoking the Shell tool to run  
`aww-cert-generate-injector.py`, show **one concise markdown table** of what will be passed.

| Column | Content |
|--------|---------|
| **Argument** | CLI flag or positional concept (use long names: `--region`, `--profile`, `--domain`, …). For default generate mode with no list/delete flag, use **`(generate/import)`** as the mode row instead of a flag. |
| **Value** | The literal value, `yes` for boolean flags that are set, or **`(script default)`** when the script supplies the value because the flag is omitted (e.g. region defaults to `us-east-1`). |

**Rules:**

- Include **one row per flag** you are passing to the script, plus rows for **implied** script defaults that matter for this run (**`--region`**, **`--profile`** / default chain, mode).
- Omit flags that are not used; do **not** paste the full shell command or a code block of the command in the user reply (internal agent tooling may still run it).
- Keep the table **short** (no paragraph text around it for this block—table only for this “inputs” block, except where other sections allow extra text below it).

## What this script does (three mutually exclusive modes)

Exactly **one** of these applies per invocation (argparse mutual exclusion on `--list-certs` vs `--delete-cert`; if neither is set, **default = generate/import**):

| Mode | Flag | Purpose |
|------|------|--------|
| **Generate + import (default)** | *(no list/delete flag)* | **ALB / web HTTPS:** OpenSSL self-signed RSA server cert (PEM), ALB/ACM-style checks, optional `acm import-certificate` for attachment to an **ALB HTTPS listener**. Writes `deploy/certs/<sanitized-fqdn>.{key,cert}.pem`. |
| **List** | `--list-certs` | **ACM inventory for ALB/web ops:** `aws acm list-certificates` (paginated). Prints Idx, Cert ID, Type, Key algorithm, In use, Renewable. Writes/overwrites cache JSON. |
| **Delete** | `--delete-cert` | **ACM cleanup:** deletes **one** cert after **y/N** (`[y/N]`, default **no**). Uses fresh list or saved cache + index—mind certs **still attached to an ALB listener**. |

## List certificates — user-visible reply (**strict**)

When the user’s goal is **only** to list ACM certificates (`--list-certs`, or natural-language equivalent such as “show my ACM certs” with no other ask):

1. In the **same** user-visible reply, show **first** the **Invocation summary table** (see above), **then** run the script via the Shell tool (**do not** paste the shell command into the chat).
2. **Then** show **only** a second markdown table — the certificate list — with these **six** columns, in this order:

   | Idx | Cert ID | Type | Key algorithm | In use | Renewable |

3. **Build the certificate table** from the script’s printed table **or** from the JSON cache file  
   `{tempdir}/midas-acm-certificate-index.json` field `certificates[]`  
   (keys: `index`, `certificate_id`, `type`, `key_algorithm`, `in_use`, `renewal_eligibility`).  
   Use the same values the script would show (`True`/`False` for in use; eligibility string or `N/A`).
4. If there are **zero** certificates, the second table is still required: header row plus **one** data row where every data cell is `—` (em dash as placeholder).
5. **Do not** add any other content between or after those two tables: no shell commands, no code fences, no “Identity: …”, no “Saved index map …”, no explanations, no follow-up questions.  
   **Exception:** if the script exits **non-zero**, send **one** plain line with the error only (no tables).

This section **overrides** the generic “report results in plain language” rule **for list-only** outcomes (except for the mandatory **Invocation summary table** + certificate table pair).

**Cache file (hardcoded name, OS temp dir):** `{tempdir}/midas-acm-certificate-index.json`  
(`tempfile.gettempdir()` — on macOS often under `/var/folders/.../T/`, not always `/tmp`.)

Each `--list-certs` run **removes** the previous cache file if present, then writes a new JSON with `version`, `region`, `profile`, `created_at`, and `certificates[]` (each row: `index`, `certificate_id`, `certificate_arn`, `type`, `key_algorithm`, `in_use`, `renewal_eligibility`).

## AWS authentication (same idea as `aws-ssm-port-forward-all.py`)

- **`--profile PROFILE`**: skips the interactive profile menu; pass e.g. `midas-dev`.
- **`default` profile choice**: means AWS default credential chain (**no** `--profile` on subprocess — script maps `default` → unset).
- **No `--profile` + TTY**: script prompts `1) midas-dev` / `2) default` / `3) custom`.
- **No `--profile` + non-TTY**: uses `$AWS_PROFILE` / `$AWS_DEFAULT_PROFILE`.
- **SSO expired**: script prints STS error and can offer **`aws sso login`**; after login it **re-runs** STS and parses the **new** JSON (do not parse the failed first response).

## Complete flag reference (agent must align user answers to these)

**Mode (pick at most one):**

| Flag | Meaning |
|------|---------|
| `--list-certs` | List ACM certs + write cache. |
| `--delete-cert` | Delete one cert (see delete rules below). |

**Common:**

| Flag | Meaning |
|------|---------|
| `-r`, `--region REGION` | AWS region (default **`us-east-1`**). |
| `--ask-region` | Prompt for region (TTY only). |
| `--profile PROFILE` | AWS CLI profile (see auth above). |

**Generate / import (default mode):**

| Flag | Meaning |
|------|---------|
| `-d`, `--domain FQDN` | Primary DNS (CN + SAN). Lowercased. |
| `--prompt-domain`, `--prompt-name` | Always prompt for primary DNS; if `-d` also set, it is the bracket default. |
| `--san DNS_NAME` | Extra DNS SAN (repeatable). |
| `--days N` | Validity days (default **365**). |
| `--key-bits` | **`2048`** or **`4096`** only (default **4096**). |
| `--skip-import` | Only write PEMs; **no** ACM import. |
| `--force` | Overwrite existing PEM files in output dir. |
| `--no-validate` | Skip post-gen modulus/SAN/SHA-256 checks (not recommended). |
| `--no-normalize-key` | Skip PKCS#8 rewrite of private key. |
| `--certificate-chain PATH` | Optional PEM chain for import. |
| `--output-dir DIR` | PEM directory (default **`<repo>/deploy/certs`**). |

**Delete-only:**

| Flag | Meaning |
|------|---------|
| `--cert-index N` | **1-based** row index. Only valid with **`--delete-cert`**. |
| `--use-saved-cert-list` | Read ARN from **last** `--list-certs` cache; **requires** `--delete-cert`. Region must **match** cache `region`. |

**Invalid combinations (script exits with error):**

- `--use-saved-cert-list` without `--delete-cert`
- `--cert-index` without `--delete-cert`

## Delete behavior (precise)

1. **Fresh list (`--delete-cert` only):** fetches ACM list, prints table, writes cache (same as list), prompts **Enter index to delete (1..N)** on TTY, then summary + **`[y/N]`** before `aws acm delete-certificate`.
2. **Non-TTY + fresh delete:** must pass **`--cert-index N`** (no prompts).
3. **`--delete-cert --use-saved-cert-list`:** loads cache JSON; **`--region`** must match cached `region`. If **`--cert-index`** omitted on TTY, reprints table from cache and prompts for index. If non-TTY, **`--cert-index`** is **required**.

## Mandatory interaction when the function is not stated

**Do not** run `aww-cert-generate-injector.py` until the user has confirmed **which function** to run, **unless** they already gave a complete, unambiguous invocation (e.g. explicit “run `--list-certs` …” with all required flags for that mode).

If the user only opens the skill (e.g. `/aws_tool`, `@aws_tool`) or speaks in vague terms (“help with certs”, “ACM”) **without** naming list / delete / generate / import:

1. **Stop.** Ask **exactly one** question: the **mode / function** picker below (**A / B / C / D** only in that first message—no script run yet).
2. Wait for their letter (or explicit equivalent, e.g. “list”).
3. **Then**, for **each remaining** required or commonly needed flag for that mode, ask **one question at a time**. Each question **must** use **lettered options** (A, B, C, …) and **must** include **at least one “custom” option** (e.g. **“D) Custom — reply with your own value for `--region`”**) so the user can type a value that is not listed.
4. Only after the full flag set is confirmed, show the **Invocation summary table** and execute (per sections above).

**Exception — fully specified runs:** If the user’s message already specifies mode **and** every flag the agent will pass (e.g. full command or equivalent natural language with region, profile, domain, etc.), the agent may run immediately after the **Invocation summary table** (still no pasted shell command in chat unless the user explicitly asked to see it).

## Agent workflow (beginner-friendly, one question at a time)

1. **Parse the user request.** Map to one of: *list*, *delete*, *generate PEM only*, *generate + import*. Prefer interpreting “create / cert / TLS / HTTPS / domain / listener” in **ALB + web HTTPS** terms per **Scope** above.
2. **Function / mode unclear?** Follow **Mandatory interaction when the function is not stated** — **never** assume defaults for mode.
3. **Any other** missing or ambiguous inputs (region, profile, domain, delete path, cert index, import vs PEM-only): **stop** and ask **exactly one** short question with **A, B, C, …** plus a **Custom** option (user supplies exact value / flag text as instructed).
4. Each preset option **must** show the **exact flag snippet or value** that will be used if that option is chosen (so the user sees the real CLI shape).
5. After you have enough information, **compose the full command** as a single line (or minimal continuation with `\`) and run it with the **Shell** tool from **repo root**.
6. **Before every script run:** show the **Invocation summary table** (flags + values / defaults) in the user-visible reply, then execute via Shell (**do not** paste the command line into chat).
7. **Report results:**  
   - **List-only (`--list-certs`):** **Invocation summary table** + certificate table only — see **List certificates — user-visible reply (strict)** (error exit → one error line only).  
   - **All other modes:** **Invocation summary table** first, then plain language or structured outcome as appropriate (e.g. ACM ARN **→ attach to ALB HTTPS listener in that region**, delete outcome, validation, SSO hints).

**Do not** put multiple unrelated questions in the **same** message (one question per message until the script is ready to run). **Do not** run destructive `--delete-cert` without explicit user confirmation via the script’s **y/N** step (the user must answer in the terminal unless they already chose non-interactive automation and understand the risk).

## Suggested question sequences (templates)

Use these as **minimum** patterns; extend with **C / D / …** and always add **Custom** when there are more than two sensible presets.

**Q1 — Function / mode (required if user did not already state it):**

- **A)** List ACM certificates (see what exists for **ALB / web** in a region) → will pass `--list-certs`
- **B)** Delete one ACM certificate (cleanup; check **not** on a live ALB listener) → will pass `--delete-cert` (then ask Q5 + index questions)
- **C)** Create **PEM files only** for an ALB/web hostname (no ACM import yet) → will pass `--skip-import` (generate mode)
- **D)** Create PEM **and** import to ACM for use on an **ALB HTTPS listener** (same region) → generate mode, **no** `--skip-import`

**Q2 — Region (ask if not already given; list / delete / generate all need a region intent):**

- **A)** `us-east-1` → `-r us-east-1` (explicit; matches script default)
- **B)** Another common preset (name one region, e.g. `us-west-2`) → `-r us-west-2`
- **C)** Custom — user replies with the **exact** region code to use after `-r` (e.g. `eu-west-1`)

**Q3 — Profile (ask if not already given):**

- **A)** `midas-dev` → `--profile midas-dev`
- **B)** Default AWS credential chain → `--profile default` *(script maps to no `--profile` on the AWS CLI subprocess)*
- **C)** Custom — user replies with the **exact** profile name for `--profile NAME`

**Q4 — Domain / hostname (generate mode only; skip for list/delete):**

This is the **HTTPS hostname** (SNI) for the **web app** or **ALB listener**—must match what clients put in the URL.

- **A)** User will type the FQDN next → you will pass `--domain <their FQDN>` (follow-up: “Reply with the full hostname, e.g. `app.example.com`”)
- **B)** Always prompt at runtime → `--prompt-domain` (optional: combine with `-d` as bracket default if they also give a hostname)
- **C)** Custom — user states literal flag line they want for domain (e.g. `--domain x.y.com` or `--prompt-domain` only)

**Q5 — Delete path (delete mode only):**

- **A)** Fresh list this session → `--delete-cert` only (no `--use-saved-cert-list`)
- **B)** Use last saved index file → `--delete-cert --use-saved-cert-list`
- **C)** Custom — user describes different flag combination they want (must stay valid per **Invalid combinations**)

**Q6 — Certificate index (delete mode, after Q5; skip if user already gave `--cert-index`):**

- **A)** I will choose interactively when the script prompts (omit `--cert-index` on the command; **TTY required**)
- **B)** Use index **N** — user replies with a single integer **N** → `--cert-index N`
- **C)** Custom — user gives the exact `--cert-index` value they need

**Generate-mode extras (ask only if relevant; one flag per question):** e.g. `--force` (overwrite PEMs), `--days`, `--key-bits`, `--san`, `--no-validate` — each as **A/B/Custom** with exact flag text shown for A and B.

## Example composed commands (copy patterns)

```bash
# List + refresh index cache
python3 .cursor/scripts/aww-cert-generate-injector.py --list-certs --profile midas-dev -r us-east-1

# Generate + import (prompt domain), same region/profile
python3 .cursor/scripts/aww-cert-generate-injector.py --prompt-domain --profile midas-dev -r us-east-1

# PEM only, explicit domain, overwrite files
python3 .cursor/scripts/aww-cert-generate-injector.py --domain app.example.com --skip-import --force

# Delete using saved list row 2 (region must match cache)
python3 .cursor/scripts/aww-cert-generate-injector.py --delete-cert --use-saved-cert-list --cert-index 2 --profile midas-dev -r us-east-1
```

## Output the user should understand

| Output | Meaning |
|--------|--------|
| **ACM certificate ARN:** | Import succeeded; attach to ALB listener in **same region**. |
| **Saved index map: …** | List/delete cache path (JSON with index ↔ ARN). |
| **ACM/ALB validation OK** | PEM passed local checks (generate mode). |
| **Skipping ACM import** | `--skip-import`; shows example `aws acm import-certificate` command. |
| **Identity: arn:aws:sts::…** | STS caller after successful auth. |

## How the user invokes this skill

Skills are loaded when their **description** matches the user’s task. The user can:

1. **@mention the skill folder** in Cursor chat, e.g. **`@aws_tool`** (or the path `.cursor/skills/aws_tool`), **or**
2. **Describe the task in natural language**, e.g.  
   - “Use **aws_tool** to list my ACM certs in us-east-1 with midas-dev”  
   - “Run **aww-cert-generate-injector** to import a cert for `foo.exlservice.com`”  
   - “Help me **delete ACM certificate index 3** using the saved list”

Then the agent should **read this `SKILL.md`**: if the user did not name the function, **always** start with **Q1 (A–D)**; then walk flags with **one A/B/C/… + Custom question per message**, and **execute** the script with the Shell tool only when the invocation is complete.

## Prerequisites (tell the user if commands fail)

- **OpenSSL** on PATH (generate mode).
- **AWS CLI v2** on PATH (list / delete / import).
- IAM permissions: **`acm:ImportCertificate`**, **`acm:ListCertificates`**, **`acm:DeleteCertificate`** as appropriate; **`sts:GetCallerIdentity`** for the auth check.

## Relationship to similarly named scripts

This repository may also contain **`acm-generate-and-import-cert.py`** with equivalent behavior. **Unless the user names that file**, default to **`aww-cert-generate-injector.py`** for this skill.
