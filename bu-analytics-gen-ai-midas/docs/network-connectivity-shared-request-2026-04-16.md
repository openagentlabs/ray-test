# Shared Connectivity Enablement — MIDAS DEV Network Load Balancer

**Document type:** Shared Infrastructure Enablement Request  
**Date:** 2026-04-16  
**Raised by:** Keith Tobin — BU Analytics / Gen-AI MIDAS team (`KEITH334747@exlservice.com`)  
**For:** EXL Core Infrastructure / Network Engineering team  
**Priority:** Medium — DEV environment access (no production impact)

---

## Overview

The MIDAS DEV application is deployed in AWS account **811391286931** (us-east-1).  
It is reachable internally via a **Network Load Balancer (NLB)** that proxies traffic to a **private Application Load Balancer (ALB)**, both of which already exist and are healthy.

The NLB is in the MIDAS VPC (`vpc-0c4d673f3e95a93eb`) which uses the corporate Transit Gateway (`tgw-0ec391fa73943d562`) for north-south routing. Traffic from the corporate network reaches this VPC only through the TGW.

This document describes two work streams and what we need from the core infrastructure team for each. The application team will take on complementary tasks within the AWS account.

---

## Asset Reference Table

_All IDs verified via AWS CLI on 2026-04-16 against account `811391286931 / us-east-1`._

| Asset | Name / ID | DNS / ARN |
|---|---|---|
| **AWS Account** | `811391286931` | — |
| **Region** | `us-east-1` | — |
| **VPC** | `vpc-0c4d673f3e95a93eb` | `10.72.134.0/23` |
| **Network Load Balancer** | `midas-dev-nlb` | `midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com` |
| NLB ARN | `arn:aws:elasticloadbalancing:us-east-1:811391286931:loadbalancer/net/midas-dev-nlb/d290764c37bb4f68` | — |
| NLB Hosted Zone | `Z26RNL4JYFTOTI` | — |
| NLB Scheme | `internal` | — |
| NLB Subnets | `subnet-0bc74e29f773eb7a4` (us-east-1a, `10.72.135.0/26`) | — |
| | `subnet-04f6c506a5098aa40` (us-east-1c, `10.72.135.64/26`) | — |
| NLB Security Group | `sg-04b9db95f904d47bd` (`midas-dev-nlb-sg`) | — |
| NLB Listener | TCP **80** → target group `midas-dev-nlb-alb-tg` (type `alb`) | — |
| **Application Load Balancer** | `midas-dev-alb` | `internal-midas-dev-alb-2046892741.us-east-1.elb.amazonaws.com` |
| ALB ARN | `arn:aws:elasticloadbalancing:us-east-1:811391286931:loadbalancer/app/midas-dev-alb/f34617a0b3c781ad` | — |
| ALB Scheme | `internal` | — |
| ALB Subnets | `subnet-05c4fce53e16da9bc` (us-east-1a, `10.72.134.0/25`) | — |
| | `subnet-04d9f5b09b2dc9425` (us-east-1c, `10.72.134.128/25`) | — |
| ALB Security Group | `sg-081477994a0163348` (`midas-dev-alb-sg`) | — |
| ALB Listener | HTTP **80** → target group `midas-dev-alb-fe-tg` (frontend pods, port 8080) | — |
| Transit Gateway | `tgw-0ec391fa73943d562` | VPC default route (`0.0.0.0/0`) |

---

## Work Stream 1 — Short Stream: Corporate Network Access via AWS-given DNS Name (HTTP/80 + HTTPS/443)

### Goal

Enable any user on the EXL corporate network to reach the MIDAS DEV application in a browser using the NLB's AWS-assigned DNS name, on both port 80 and port 443.

### Current state

- The NLB currently has **one listener: TCP 80**.  
- The NLB security group (`sg-04b9db95f904d47bd`) already allows TCP 80 inbound from three known CIDRs: `10.54.74.117/32`, `10.54.67.114/32`, `10.90.12.0/22`.  
- The ALB has **one listener: HTTP 80**; no TLS listener exists yet.  
- There is **no TCP 443 / HTTPS listener** on either load balancer at this time.  
- The NLB resides in the MIDAS VPC; corporate traffic reaches it only via the TGW.

### What the MIDAS team will do (our responsibility)

| # | Action | Owner |
|---|---|---|
| 1 | Add a **TCP 443 listener** to the NLB forwarding to the ALB | MIDAS app team |
| 2 | Add an **HTTPS 443 listener** to the ALB (self-signed or ACM cert initially; to be replaced in WS2) | MIDAS app team |
| 3 | Update `sg-04b9db95f904d47bd` inbound rules to allow TCP **443** from the EXL corporate CIDR range (see below) | MIDAS app team — needs the confirmed EXL corporate CIDR range from infrastructure team |
| 4 | Update `sg-081477994a0163348` inbound rules to allow TCP **443** from the NLB security group | MIDAS app team |

### What we need from core infrastructure

> **Please action the following items:**

**1.1 — Confirm the full EXL corporate CIDR range(s) for the TGW**

The NLB security group currently has narrow individual CIDRs (`10.54.74.117/32`, etc.). To allow all corporate users we need the canonical EXL corporate network summary CIDR(s) that traverse the Transit Gateway into this VPC. Please confirm or supply the CIDR block(s) to add.

**1.2 — Confirm TGW routing allows TCP 443 to VPC CIDR `10.72.134.0/23`**

The TGW route tables should already permit all TCP from corporate → VPC (since port 80 can traverse); please confirm port 443 is not subject to any additional TGW-level ACL or policy that would block it.

**1.3 — Blackspider / web proxy: allow outbound to the NLB DNS name on port 80 and 443**

The NLB DNS name is:

```
midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com
```

If EXL corporate users browse via the Blackspider (Symantec/Broadcom) web filtering proxy, an allow rule is required for this hostname on ports 80 and 443. Please raise the Blackspider policy change to permit:

- **Destination hostname:** `midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com`  
- **Ports:** TCP 80 and TCP 443  
- **Source:** All EXL corporate network (internal users)  
- **Direction:** Outbound (user → AWS)

**1.4 — DNS resolution for the AWS-given name from corporate desktops**

The hostname above is an AWS-managed DNS entry (Route 53 public hosted zone for `*.elb.us-east-1.amazonaws.com`). Please confirm corporate DNS resolvers forward this to public DNS, or whitelist resolution of `*.elb.us-east-1.amazonaws.com` if corporate DNS does not forward unknown names externally.

---

## Work Stream 2 — Longer Stream: Custom Domain `keith.tobin.com`, Certificate, and Blackspider Policy

### Goal

Expose MIDAS DEV at `https://keith.tobin.com` with a valid TLS certificate, registered in corporate DNS pointing to the NLB, and allowed through the Blackspider firewall for all EXL network users.

### What the MIDAS team will do (our responsibility)

| # | Action | Owner |
|---|---|---|
| 1 | Request an ACM certificate for `keith.tobin.com` in account `811391286931 / us-east-1` | MIDAS app team — needs DNS validation record created by infra/DNS team |
| 2 | Configure HTTPS 443 listener on NLB / ALB to use the ACM cert once issued | MIDAS app team |
| 3 | Update ALB routing rules and Host headers for `keith.tobin.com` | MIDAS app team |

### What we need from core infrastructure

> **Please action the following items:**

**2.1 — Issue / procure a TLS certificate for `keith.tobin.com`**

Options (please advise which is preferred under EXL policy):

- **Option A (AWS ACM — preferred):** The MIDAS team requests an ACM certificate for `keith.tobin.com` in account `811391286931`. ACM will provide a DNS CNAME validation record that must be added to the authoritative DNS zone for `keith.tobin.com`. **We need the infrastructure/DNS team to add this CNAME** to complete validation.
- **Option B (EXL internal CA / Entrust):** If EXL policy requires certs to be issued from the corporate CA, please raise the certificate order for `keith.tobin.com` and provide the signed certificate + chain for import into ACM.

**2.2 — Corporate DNS: create a CNAME (or Alias) pointing `keith.tobin.com` → NLB DNS name**

Once the certificate is in place, corporate DNS must resolve `keith.tobin.com` to the NLB. Please create:

```
keith.tobin.com  CNAME  midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com
```

Or, if the DNS platform supports AWS alias-style records to an internal ELB, that is equally acceptable. The NLB Route 53 hosted zone is `Z26RNL4JYFTOTI`.

> **Note:** The NLB is `internal` (RFC 1918 target IPs only). The DNS entry must be added in the **corporate internal DNS** zone that EXL desktops query — not in a public zone.

**2.3 — Blackspider / web proxy: allow outbound to `keith.tobin.com` on port 80 and 443**

Please raise a Blackspider policy change to permit:

- **Destination hostname:** `keith.tobin.com`  
- **Ports:** TCP 80 and TCP 443  
- **Source:** All EXL network (any internal user)  
- **Direction:** Outbound (user → AWS internal via TGW)

**2.4 — Confirm `tobin.com` / `keith.tobin.com` is an EXL-managed DNS zone (or advise alternative)**

If `tobin.com` is not an EXL-controlled zone, please advise the correct domain naming convention under which a personal/team subdomain can be registered (e.g. `keith-midas.exlanalytics.com` or similar). The MIDAS team can adopt whichever naming pattern infrastructure prefers.

---

## Traffic Flow — Architecture Context

```
[Corporate user / laptop]
        |
        | TCP 80 / 443 (via TGW)
        v
[NLB: midas-dev-nlb] — sg-04b9db95f904d47bd
  DNS: midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com
  Subnets: subnet-0bc74e29f773eb7a4 (1a), subnet-04f6c506a5098aa40 (1c)
  Listener: TCP 80 → target-type ALB
  (planned) Listener: TCP 443 → target-type ALB
        |
        | TCP 80 / 443 (intra-VPC)
        v
[ALB: midas-dev-alb] — sg-081477994a0163348
  DNS: internal-midas-dev-alb-2046892741.us-east-1.elb.amazonaws.com
  Subnets: subnet-05c4fce53e16da9bc (1a), subnet-04d9f5b09b2dc9425 (1c)
  Listener: HTTP 80 → frontend pods (port 8080)
  (planned) Listener: HTTPS 443 → frontend pods (port 8080) with ACM cert
        |
        | HTTP 8080 / 8000 / 8001
        v
[EKS pods — sg-0bcffb89cba7c228f]
  Frontend : port 8080
  Backend  : port 8000
  GraphQL  : port 8001
```

---

## Summary of Asks by Team

### Core Infrastructure / Network Engineering team

| Stream | Item | Action needed |
|---|---|---|
| WS1 | 1.1 | Confirm / provide full corporate CIDR range(s) via TGW |
| WS1 | 1.2 | Confirm TCP 443 permitted at TGW level to `10.72.134.0/23` |
| WS1 | 1.3 | Blackspider allow-rule: `midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com` :80/:443, all EXL internal |
| WS1 | 1.4 | Confirm / enable `*.elb.us-east-1.amazonaws.com` DNS resolution from corporate desktops |
| WS2 | 2.1 | ACM DNS validation CNAME for `keith.tobin.com` (or issue via corporate CA) |
| WS2 | 2.2 | Corporate internal DNS CNAME: `keith.tobin.com` → NLB DNS name |
| WS2 | 2.3 | Blackspider allow-rule: `keith.tobin.com` :80/:443, all EXL internal |
| WS2 | 2.4 | Confirm `keith.tobin.com` is valid domain / advise preferred naming convention |

### MIDAS application team (Keith Tobin)

| Stream | Item | Action needed |
|---|---|---|
| WS1 | — | Add TCP 443 listener to NLB |
| WS1 | — | Add HTTPS 443 listener to ALB |
| WS1 | — | Update NLB/ALB security groups for port 443 once corporate CIDR confirmed |
| WS2 | — | Request ACM cert for `keith.tobin.com` (pending 2.1 / 2.4 answer) |
| WS2 | — | Wire ACM cert to ALB HTTPS listener |
| WS2 | — | Update ALB Host-based routing rules for `keith.tobin.com` |

---

## Contact

**MIDAS team contact:** Keith Tobin — `KEITH334747@exlservice.com`  
**AWS account:** `811391286931` | **Region:** `us-east-1` | **Environment:** DEV

_This is a shared-responsibility request. Infrastructure and application team actions are explicitly called out above so both sides can track progress in parallel._
