# Fabrikam Aerial Logistics — Information Security Policy

**Policy owner:** Chief Information Security Officer (Tomasz Brennan)
**Version:** 3.1 — last reviewed March 2, 2026

## 1. Passwords and authentication

- Passwords must be at least **14 characters**. Passphrases are encouraged.
- Passwords are **not** subject to periodic forced rotation; they must be changed immediately if a compromise is suspected.
- Multi-factor authentication (MFA) is mandatory for all accounts. Only **phishing-resistant** methods (FIDO2 security keys or platform passkeys) are allowed for administrators.
- SMS-based MFA was retired on **October 1, 2025**.

## 2. Devices

- All laptops must use full-disk encryption and be enrolled in device management.
- Screens must auto-lock after **5 minutes** of inactivity.
- Personal devices may access email and chat only; they may not access flight-control systems.

## 3. Data classification

| Level | Examples | Allowed storage |
|-------|----------|-----------------|
| Public | Marketing site, press releases | Anywhere |
| Internal | Handbook, org charts | Company tenant only |
| Confidential | Customer contracts, pricing exceptions | Company tenant, access-restricted |
| Restricted | Flight-control firmware signing keys, patient manifests | HSM or isolated enclave only |

Patient manifests carried by Heron H1 missions are classified **Restricted** and must be deleted **90 days** after delivery confirmation.

## 4. Incident reporting

Report suspected security incidents within **1 hour** of discovery to `security@fabrikam-aerial.example` or the 24/7 hotline at extension **7777**. Do not attempt to investigate on your own.

## 5. Acceptable AI use

Employees may use the company-approved AI assistant for Internal data. Confidential and Restricted data must **never** be pasted into public AI tools.
