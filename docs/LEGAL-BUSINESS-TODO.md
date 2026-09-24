# Sitemyra legal and business information TODO

This checklist is intentionally explicit. The repository does not contain
verified legal-entity information, so the public legal pages do not guess it.

## Before accepting paid subscriptions

Have a qualified Greek accountant and, where appropriate, a legal professional
confirm:

- [ ] Legal operator name and whether Sitemyra is operated by an individual or
      a registered business
- [ ] Business status, registration number, and any required GEMI details
- [ ] Business/contact address required for invoices or consumer information
- [ ] VAT status and VAT number, if applicable
- [ ] Invoicing details, currency/tax handling, and recordkeeping process
- [ ] Governing law, courts, dispute process, and mandatory consumer rights
- [ ] Cancellation and refund policy, including what happens after a downgrade
- [ ] Payment provider terms and the exact customer-facing billing disclosures
- [ ] Supervisory authority or complaint route where required
- [ ] Hosting/edge provider, international-transfer details, and backup retention

## Contact configuration

The public contact page supports a verified address through
`NEXT_PUBLIC_CONTACT_EMAIL`. Set it only after confirming that the mailbox is
monitored and appropriate for general questions. Transactional email
`Reply-To` is separately opt-in through `EMAIL_REPLY_TO`; do not assume the
transactional sender is a support inbox.

## Website status

The legal pages are written as transparent product summaries. They should be
reviewed and updated after the business setup is verified. They are not a claim
that the service is fully compliant or legally ready.
