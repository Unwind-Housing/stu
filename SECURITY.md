# Security

Stu holds personal information about applicants and homeowners, so please report problems privately.

## Reporting a problem

Use **Security > Report a vulnerability** on this repository's GitHub page (a private report to the maintainers). Please don't open a public issue for a security problem, and never paste real household data, sign-in details or a flow's HTTP address into an issue or pull request.

## What must never be committed

- Credentials, `.env` files, tokens, certificates.
- A flow's HTTP address. Anyone who has it can post to the flow, so treat it like a password. If one leaks, change it: open the flow in Power Automate, re-save the trigger to get a new address, and paste the new one into the form.
- Anything in `clients/` except the `clients/example/` folder, and anything in `export/`.
- Real people's details in tests, examples or screenshots. Use made-up names at `example.com`.

## Data rules built into the design

- No Social Security numbers or bank account numbers in Dataverse.
- Applicants' uploaded documents stay in the forms platform until the household is certified.
- Household documents go in a restricted SharePoint library. Dataverse security does not carry over to SharePoint: set the library's permissions by hand (see `INSTALL.md`).
