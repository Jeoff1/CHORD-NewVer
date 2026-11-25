# Phase 9B click-through test

A manual run through the Church Platform ([[0014-church-platform]],
[[Phase-9B-Plan]]) in a browser, after the automated checks pass. Each
step says what to do and what you should see. Tick a step when it
behaves as written; note anything else in the [[Development-Log]].

**Before you start**

- Run `.\scripts\check.ps1` on branch `phase-9b-church-platform`; it must
  pass.
- Run `.\.venv\Scripts\python.exe manage.py migrate`, then start the site
  (`manage.py runserver`) and the search worker (`manage.py run_worker`).
- Have two browsers, or one normal and one private window, so two people
  can be signed in at once. Call them **window A** and **window B**.
- You need the existing church's Administrator account. Below, the
  existing church is "the first church".

## 1. The first church after the upgrade

- [ ] **1.1** In window A, sign in as the first church's Administrator.
  The dashboard shows the first church, with every record as before:
  services, songs, lineups, members, teams, occasions, announcements.
- [ ] **1.2** Open Settings, then **Public homepage**. "Show the church
  publicly" is **off**, "Show upcoming services" is off, and "Accept
  requests from people outside the church" is on.
- [ ] **1.3** Open Settings, then **Modules**. All five Modules have a
  switch; none says "Not available yet".
- [ ] **1.4** Sign out. Open `/churches/`. The first church is **not**
  listed. Open `/churches/<its slug>/` (the slug is its name in lower
  case with dashes): **404**.

## 2. Make the first church public

- [ ] **2.1** Sign in again as its Administrator. In **Public homepage**,
  switch **"Show the church publicly" on**, write two lines in About (put
  `<b>bold</b>` in one), and save.
- [ ] **2.2** Open Occasions, then Settings, then Occasion types. Edit
  "Wedding": tick **Active** and **Offered publicly**, and save. Leave the
  others as they are.
- [ ] **2.3** Post an announcement to Everyone with **"Also show it on the
  church's homepage"** ticked, and another without it.
- [ ] **2.4** Sign out. Open `/churches/`: the first church is listed.
  Search for part of its name in capitals: still found. Open it.
- [ ] **2.5** The homepage shows the name, contact details, About on two
  lines with `<b>bold</b>` printed as text, the public announcement only,
  and "Wedding" with **Request this service**. It shows **no** songs,
  lineups, chord sheets, lyrics, themes, members or teams.
- [ ] **2.6** Back as the Administrator, switch **"Show upcoming
  services"** on. Signed out, the homepage now lists coming services by
  date, time and kind only, never their name or theme.

## 3. Register a second church

- [ ] **3.1** In window B (signed out), open the landing page and press
  **Sign in your church**. Give a church name (for example "Hilltop
  Chapel") and a new account. No question asks about the church's
  denomination or tradition.
- [ ] **3.2** You land in the setup wizard, step 1 of 4. Finish all four
  steps. In **Modules**, Members and Teams say **"Not available yet"**
  with no switch.
- [ ] **3.3** The dashboard shows Hilltop Chapel with nothing of the
  first church: open Worship, Songs, Occasions, Announcements, Users and
  Roles; none shows a record of the first church.
- [ ] **3.4** Open `/members/` and `/teams/`: **404**.
- [ ] **3.5** In window A, copy the address of one of the first church's
  services (or songs). Paste it into window B: **404**.
- [ ] **3.6** Register another church called "Register": its address is
  `/churches/register-church/`, and `/churches/register/` is still the
  registration page.

## 4. Accounts across churches

- [ ] **4.1** In a third, private window, open **Create an account**
  from the sign-in page and make one. Its home says "You're not part of a
  church yet", with links to the churches and My requests.
- [ ] **4.2** In window A, open Users, then **Add an existing account**.
  Type part of that account's username: refused ("No account has that
  username or email"). Type the whole username, give it Team Member, and
  add it. It now appears in Users.
- [ ] **4.3** In window B, add the same account to Hilltop Chapel the same
  way. Back in window A, open that user: their username, name, email and
  Active are **read-only**, there is no **Set a new password** link, and
  their History says **"Shared account: sign-ins not shown"**.
- [ ] **4.4** Sign that account in. Its user menu shows **Working in** with
  both churches. Choose Hilltop Chapel: the dashboard changes to it.
- [ ] **4.5** In window B, remove that person from Hilltop Chapel. In the
  person's window, open any page: they are back in the first church, and
  the switcher is gone.
- [ ] **4.6** Sign them out and in again: they start in the first church.
- [ ] **4.7** In window B, open Hilltop Chapel's only Administrator (the
  account that registered it) and press **Remove from this church**:
  refused. Take away their Administrator role: refused.

## 5. Requests from the homepage

- [ ] **5.1** In the private window (signed out), open the first church's
  homepage and press **Request this service** on Wedding. You are asked to
  sign in; after signing in you are back on the request form.
- [ ] **5.2** Choose a time that overlaps one of the first church's
  services. The form says only **"That time is already booked"**, without
  naming the service.
- [ ] **5.3** Choose a free time and send. You land on **My requests**,
  which shows the request with the church's name.
- [ ] **5.4** In window A, the Pastor (or anyone who approves requests)
  has a notification of the new request. Approve it.
- [ ] **5.5** In the private window, a notification says it was
  approved; My requests shows "Approved" with no Withdraw button.
- [ ] **5.6** Send another request, then press **Withdraw** on it: it
  shows "Withdrawn".
- [ ] **5.7** In window A, switch off "Accept requests from people outside
  the church". In the private window, the homepage shows no request
  buttons, and the request form's address now says "Requests from its
  own people only".
- [ ] **5.8** Change the request form's address to the number of
  "Baptism" (not offered publicly): **404**.

## 6. Keep it private again

- [ ] **6.1** In window A, switch **"Show the church publicly" off**.
  Signed out, the first church is gone from `/churches/`, and its homepage
  and request addresses give **404**.
- [ ] **6.2** Upload a logo named after a person (such as
  `ana-passport.png`). Right-click it and copy its address: it is
  `/media/church/<random letters>.png`, with no name in it. Try a text
  file renamed to `.png`: refused.

When every step is ticked, tell the owner; Phase 9B is merged into
`master` only when the owner says so.
