# Email delivery through Resend HTTPS

Railway Free, Trial and Hobby block outbound SMTP. This app supports Resend's
HTTPS API without changing the Gmail ERP import script or existing users.

## Setup

1. Create/sign into Resend using the first administrator email. For this
   deployment that is `ashwinnn1995@gmail.com`.
2. In Resend, create an API key with **Sending access**, restricted to the
   intended domain where possible. Enter it yourself in Railway as
   `RESEND_API_KEY`; never put it in chat, source code or a screenshot.
3. In the app service's Railway Variables, set these individually:
   - `MAIL_PROVIDER=resend`
   - `RESEND_FROM_EMAIL=Performance Dashboard <onboarding@resend.dev>` for testing.
4. Deploy the variables. Request a sign-in link to the email associated with
   your Resend account. Check Resend's delivery dashboard and the receiving
   inbox/spam folder, then use the link yourself.
5. For other dashboard users, verify a domain you control in Resend, add its
   required DNS records, and change `RESEND_FROM_EMAIL` to a sender on that
   domain. Gmail addresses cannot be verified as your own sending domain.

The `resend.dev` sender is for testing only and can send only to your Resend
account email. API acceptance alone does not prove inbox delivery.

Keep `ADMIN_PASSWORD` until email sign-in has been tested successfully. Removing
that bootstrap variable does not erase existing users' stored passwords.

## Behavior and troubleshooting

- `MAIL_PROVIDER` defaults to `smtp` for existing installations; `resend` selects
  HTTPS explicitly. Resend never falls back to blocked SMTP after a failure.
- Both `RESEND_API_KEY` and `RESEND_FROM_EMAIL` must be present before email
  sign-in is offered. Presence means configured, not verified delivery.
- A failed send does not crash the app or reveal whether an email is registered.
- Railway logs show the HTTP status for API errors, but never response bodies,
  API keys or sign-in links. Inspect the Resend dashboard for provider details.
- HTTP 401/403: check the API key permissions and sender/recipient restrictions.
- HTTP 429: check Resend rate limits. Request a fresh link later; the app does
  not retry automatically, to avoid sending duplicates.
- Gmail continues receiving ERP reports. Its Apps Script posts to `/api/ingest`
  every 3 hours after the separate feed setup; no Resend key is used there.

References: https://resend.com/docs/api-reference/emails/send-email and
https://resend.com/docs/knowledge-base/403-error-resend-dev-domain
