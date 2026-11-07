/**
 * ERP Mail Collector  (Google Apps Script)
 * Runs inside ashwin0project@gmail.com. Every 3 hours it:
 *   1. finds report emails carrying the Gmail label "ERP-Reports" that arrived since its last bookmark,
 *   2. sends each Excel attachment to the dashboard app on Railway,
 *   3. moves the bookmark forward only after the app has answered.
 * The ERP sends the same subject and file name every time, so Gmail stacks the emails in one conversation.
 * This script therefore works by TIME (a bookmark) and keeps only a short list of recent emails, so its memory never grows.
 * If an email is ever sent twice, the app ignores the repeat (identical file = duplicate).
 *
 * ONE-TIME SETUP (see the guide): paste this file, set the Script properties, run testSetup, then run installTrigger.
 *
 * Script properties to set (Project Settings > Script properties). Nothing secret is written in this file:
 *   ALLOWED_SENDERS : address(es) the report emails come from (the ERP's sending address), comma separated.
 *                     Use * to accept any sender: the script only ever reads emails that carry the ERP-Reports label,
 *                     so the Gmail filter (subject line) alone decides what is taken. Safer: keep the ERP's address(es) listed.
 *   REPORT_QUERY    : optional Gmail search for report emails; the collector labels matches from the last 48 hours.
 *   ALERT_EMAIL     : who is emailed when something fails repeatedly
 *   SUBJECT_CONTAINS: optional. Only emails whose subject contains this text are used, e.g.  Shipment Register
 *   APP_URL         : the dashboard app's ingest address, for example https://your-app.up.railway.app/api/ingest (leave empty until the app is live)
 *   INGEST_SECRET   : the shared password between this script and the app (given to you once the app is live)
 */
const CONFIG = {
  TRIGGER_HOURS: 3,                  // automatic mailbox refresh interval
  LABEL_TODO: 'ERP-Reports',          // the Gmail filter puts this label on incoming report emails
  LABEL_FAILED: 'ERP-Reports-Failed', // emails that could not be processed after all tries
  MAX_ATTEMPTS: 5,                    // tries per email before it is parked and you are alerted
  MAX_MESSAGES_PER_RUN: 40,
  MAX_ATTACHMENT_MB: 20,
  OVERLAP_MIN: 10,                    // re-look this far behind the bookmark, to be safe
  FIRST_RUN_LOOKBACK_HOURS: 48,       // on the very first run, pick up emails from the last two days
};

// ------------------------------------------------------------------ main run
function collectReports() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return;                        // another run is still going
  try {
    const p = props_();
    if (!p.ALLOWED_SENDERS) { alert_('Report collector is not set up', 'ALLOWED_SENDERS is empty, so no email is accepted. Set it in Script properties.'); return; }
    if (!p.APP_URL || !p.INGEST_SECRET) { console.log('APP_URL / INGEST_SECRET not set yet: nothing is sent. Run testSetup to check the email side.'); return; }
    const reportLabel = label_(CONFIG.LABEL_TODO);
    if (p.REPORT_QUERY) {
      GmailApp.search('(' + p.REPORT_QUERY + ') newer_than:2d', 0, 100).forEach(t => t.addLabel(reportLabel));
    }
    const allowed = p.ALLOWED_SENDERS.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
    const st = state_(), failedLabel = label_(CONFIG.LABEL_FAILED);
    const found = candidates_(st);
    let advance = true, newCursor = st.cursor;
    found.slice(0, CONFIG.MAX_MESSAGES_PER_RUN).forEach(c => {
      const id = c.msg.getId(), when = c.msg.getDate().getTime();
      try {
        processMessage_(c.msg, allowed, p);
        st.done.push(id); delete st.tries[id];
        if (advance) newCursor = Math.max(newCursor, when);
      } catch (err) {
        const n = (st.tries[id] || 0) + 1; st.tries[id] = n;
        console.error('Message ' + id + ' attempt ' + n + ': ' + err);
        if (n >= CONFIG.MAX_ATTEMPTS) {                    // parked: stop retrying, tell a person
          c.thread.addLabel(failedLabel); st.done.push(id); delete st.tries[id];
          if (advance) newCursor = Math.max(newCursor, when);
          alert_('Report email could not be processed', 'Subject: ' + c.msg.getSubject() + '\nFrom: ' + c.msg.getFrom() + '\nAfter ' + n + ' tries: ' + err + '\n\nUse the admin portal to upload the file manually.');
        } else { advance = false; }                        // keep the bookmark behind this email so it is retried
      }
    });
    st.cursor = newCursor; saveState_(st);
  } finally { lock.releaseLock(); }
}

/** Emails under the label that arrived after the bookmark and have not been handled, oldest first. */
function candidates_(st) {
  const since = new Date(st.cursor - CONFIG.OVERLAP_MIN * 60000);
  const day = Utilities.formatDate(new Date(since.getTime() - 86400000), 'GMT', 'yyyy/MM/dd');
  const threads = GmailApp.search('label:' + CONFIG.LABEL_TODO + ' has:attachment filename:xlsx after:' + day, 0, 50);
  const out = [];
  threads.forEach(t => t.getMessages().forEach(m => { if (m.getDate() >= since && st.done.indexOf(m.getId()) < 0) out.push({msg: m, thread: t}); }));
  return out.sort((a, b) => a.msg.getDate() - b.msg.getDate());
}

function processMessage_(msg, allowed, p) {
  const sender = email_(msg.getFrom());
  if (!allowed.includes('*') && !allowed.includes(sender)) { console.log('Ignored a message from ' + sender + ' (not in ALLOWED_SENDERS)'); return; }
  const need = (p.SUBJECT_CONTAINS || '').trim().toLowerCase();
  if (need && msg.getSubject().toLowerCase().indexOf(need) < 0) { console.log('Ignored "' + msg.getSubject() + '" (subject does not contain "' + p.SUBJECT_CONTAINS + '")'); return; }
  msg.getAttachments({includeInlineImages: false}).filter(a => /\.xlsx$/i.test(a.getName())).forEach(att => sendToApp_(msg, att, p));
}

function sendToApp_(msg, att, p) {
  if (att.getSize() > CONFIG.MAX_ATTACHMENT_MB * 1048576) throw new Error('Attachment "' + att.getName() + '" is larger than ' + CONFIG.MAX_ATTACHMENT_MB + ' MB');
  const res = UrlFetchApp.fetch(p.APP_URL, {
    method: 'post',
    headers: {Authorization: 'Bearer ' + p.INGEST_SECRET},
    payload: {
      file: att.copyBlob(), file_name: att.getName(), source: 'email', gmail_message_id: msg.getId(),
      gmail_date: msg.getDate().toISOString(), subject: msg.getSubject(), sender: msg.getFrom(),
    },
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code >= 500 || code === 429 || code === 408) throw new Error('App not available (HTTP ' + code + ')');   // try again next run
  if (code === 401 || code === 403) throw new Error('The app refused the password (check INGEST_SECRET)');
  let r;
  try { r = JSON.parse(res.getContentText()); } catch (e) { throw new Error('Unreadable answer from the app (HTTP ' + code + ')'); }
  if (r.status === 'queued' || r.status === 'promoted' || r.status === 'duplicate' || r.status === 'stale') {
    console.log(att.getName() + ': ' + r.status + (r.message ? ' (' + r.message + ')' : ''));
  } else {                                                  // failed, needs_review, rejected, unrecognised: the app keeps the file
    alert_('A report needs attention', att.getName() + ' was ' + r.status + ': ' + (r.message || '') + '\n\nOpen the admin portal > Imports to review it, approve it or upload a corrected file.');
  }
}

// ------------------------------------------------------------------ small memory (one property, never grows)
function state_() {
  let s = {}; try { s = JSON.parse(PropertiesService.getScriptProperties().getProperty('STATE') || '{}'); } catch (e) { s = {}; }
  s.cursor = s.cursor || (Date.now() - CONFIG.FIRST_RUN_LOOKBACK_HOURS * 3600000); s.done = s.done || []; s.tries = s.tries || {};
  return s;
}
function saveState_(s) {
  s.done = s.done.slice(-150);
  const keys = Object.keys(s.tries); if (keys.length > 100) keys.slice(0, keys.length - 100).forEach(k => { delete s.tries[k]; });
  PropertiesService.getScriptProperties().setProperty('STATE', JSON.stringify(s));
}

// ------------------------------------------------------------------ helpers
function props_() { return PropertiesService.getScriptProperties().getProperties(); }
function label_(n) { return GmailApp.getUserLabelByName(n) || GmailApp.createLabel(n); }
function email_(from) { const m = /<([^>]+)>/.exec(from); return (m ? m[1] : from).trim().toLowerCase(); }
function alert_(subject, body) {
  const to = props_().ALERT_EMAIL || Session.getEffectiveUser().getEmail();
  try { MailApp.sendEmail(to, '[ERP dashboard] ' + subject, body); } catch (e) { console.error('Could not send alert: ' + e); }
}

// ------------------------------------------------------------------ run these yourself
/** Run this first. Changes nothing: it checks the label and the report emails of the last 3 days and prints a report in the log. */
function testSetup() {
  const p = props_(), out = [];
  out.push(p.ALLOWED_SENDERS ? 'OK   ALLOWED_SENDERS = ' + p.ALLOWED_SENDERS : 'FAIL ALLOWED_SENDERS is empty');
  out.push(p.ALERT_EMAIL ? 'OK   ALERT_EMAIL = ' + p.ALERT_EMAIL : 'NOTE ALERT_EMAIL is empty (alerts will go to this Gmail account)');
  out.push(p.APP_URL && p.INGEST_SECRET ? 'OK   APP_URL and INGEST_SECRET are set' : 'NOTE APP_URL / INGEST_SECRET not set yet: nothing will be sent');
  if (p.REPORT_QUERY) out.push('OK   REPORT_QUERY is set: matching reports from the last 48 hours are labelled automatically on collection.');
  const allowed = (p.ALLOWED_SENDERS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
  const query = p.REPORT_QUERY ? '(' + p.REPORT_QUERY + ') newer_than:2d' : 'label:' + CONFIG.LABEL_TODO + ' newer_than:3d';
  const threads = GmailApp.search(query, 0, 30); let reports = 0, n = 0;
  threads.forEach(t => t.getMessages().forEach(m => {
    if (m.getDate().getTime() < Date.now() - CONFIG.FIRST_RUN_LOOKBACK_HOURS * 3600000) return;
    const s = email_(m.getFrom()), xl = m.getAttachments({includeInlineImages: false}).filter(a => /\.xlsx$/i.test(a.getName()));
    if (!allowed.includes('*') && !allowed.includes(s)) return;
    reports += xl.length; n++;
    out.push('       - ' + Utilities.formatDate(m.getDate(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm') + ' | from ' + s + ' | subject "' + m.getSubject() + '" | Excel files: ' + (xl.map(a => a.getName() + ' (' + Math.round(a.getSize() / 1024) + ' KB)').join('; ') || 'none'));
  }));
  out.push(reports ? 'OK   ' + n + ' email(s) with ' + reports + ' Excel attachment(s) found' : 'FAIL no Excel attachments found: check the report query and incoming ERP emails');
  console.log(out.join('\n'));
  return out.join('\n');
}

/** Run once after testSetup looks right AND the app is live: checks for new report emails every 3 hours. */
function installTrigger() {
  const existing = ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'collectReports');
  if (existing.length) { console.log('Collector trigger already exists; inspect Triggers before adding another.'); return; }
  ScriptApp.newTrigger('collectReports').timeBased().everyHours(CONFIG.TRIGGER_HOURS).create();
  console.log('Installed: collectReports now runs every ' + CONFIG.TRIGGER_HOURS + ' hours.');
}
