🚀 Station 404
<div align="center">








A Next-Generation Discord Bot with Integrated Web Dashboard
Where Strategy Meets Social Deduction
Features • Gameplay • Commands • Installation • Dashboard
</div>

Overview
Station 404 is a sophisticated Discord bot that transforms your server into an immersive social deduction game arena. Inspired by classics like Among Us, it combines strategic gameplay, economy management, and a powerful web-based administration panel — all seamlessly integrated.
Whether you're commanding a round as the imposter or building your fortune through the shop system, Station 404 delivers a rich, interactive experience with enterprise-grade reliability.
✨ Features
🎮 Core Gameplay
🎭 Imposter System — Secretly assigned roles with phase-based rotations
👁️ Witness Mechanics — Players who witness crimes can report or stay silent
⚔️ Combat & Robbery — Strategic elimination and theft mechanics with stealth options
🔄 Dynamic Rounds — Prep → Active → End phases with automatic management
📊 Live Statistics — Real-time tracking of kills, robberies, and earnings
🛒 Advanced Economy
💰 Dual Currency System — Pocket Credits (spendable) & Vault Bonds (secure)
🎫 Usage-Based Passes — TOT, Daily, and All-Access passes with configurable limits
📦 Mystery Boxes — Bulk-openable loot containers with weighted rarity tables
🔐 Approval System — Admin-controlled item purchases with unique codes
🏪 Web Shop — Full-featured online store synced with Discord
Inventory & Items
** Active Items** — Rob Proof, Shield Boost, Radar Ping, Stealth Rob, Bank Pass
🎁 Loot Tables — Customizable rarity distribution (Common/Rare/Epic/Legendary)
️ Auto-Cleanup — Round-based DM management (preserves pinned messages)
🎛️ Admin Dashboard
📊 Real-Time Overview — Live game state, player counts, and recent events
👥 Player Management — Edit balances, jail/release, respawn, move rooms
** Shop CRUD** — Create, edit, delete items without code changes
🔐 Approval Center — Bulk approve/reject with Discord DM notifications
📜 Event Log — Complete audit trail of all game actions
🎫 Pass Configuration — Set min credits, max accounts per pass type
🤖 Bot Features
⚡ Slash Commands — Modern Discord UI with auto-complete
🔔 Smart Notifications — Tracked DMs that clean up after rounds
🛡️ Auto-Pin System — Approval/rejection messages preserved permanently
📡 Web Integration — Seamless Discord ↔ Web server communication
🔄 Auto-Restart — Systemd services for 24/7 uptime
🎯 Gameplay
The Cycle
mermaid





Code
Preview
Phase Breakdown
1️⃣ Prep Phase (5 minutes)
Players /clockin to join the round
Imposter is secretly assigned
Final preparations before chaos begins
2️⃣ Active Phase (30 minutes)
Imposter: Eliminate crew, steal credits, avoid detection
Crew: Complete tasks, gather loot, survive
Witnesses: Report crimes or stay silent
Robbers: Strike when witnesses aren't looking
3️⃣ Round End
All DMs cleaned (except pinned approvals)
Players respawned
Stats recorded
Ready for next round
Key Mechanics
Mechanic
Description
🎭 Imposter Rotation
New imposter chosen each phase; jailed imposters trigger emergency rotation
👁️ Witness System
Living players in the same room get DM buttons to REPORT or LOOK AWAY
⚖️ Justice System
Reported players jailed with escalating sentences (2/3/4 min)
💀 Death & Respawn
Killed players lose pocket credits; auto-respawn after cooldown
** Economy**
Earn through tasks, loot, robbery; spend in shop or save in vault
📜 Commands
👤 Registration & Profile
123
** Gameplay**
123456
⚔️ Combat
12
** Shop & Inventory**
1234
Special Usage:
1234
👑 Admin Commands
12
Web Dashboard
Access your server's control panel at: http://YOUR_SERVER_IP:PORT
Dashboard Sections
📊 Overview
Current round status & phase
Player count (total/on duty)
Live event feed
Game statistics
👥 Players
Searchable player list
Edit pocket credits & vault bonds
Manual jail/release
Room reassignment
Kill/respawn controls
** Shop Management**
Create/edit/delete items
Set prices, rarity, stock limits
Configure loot weights
Toggle approval requirements
🔐 Approvals
Pending requests with player names
One-click approve/reject
Auto-DM notifications
Approval history
🎫 Pass Settings
Configure max accounts per pass
Set minimum credit requirements
Toggle pass availability
Real-time usage tracking
📜 Event Log
Filterable by event type
Full audit trail
Exportable data
Timestamp & actor tracking
🛠️ Installation
Prerequisites
Python 3.11+
Discord Bot Token (Get it here)
SQLite3 (included with Python)
Git
Quick Start
bash
12
Environment Variables (.env)
env
1234567891011121314
🚀 Deployment (Cloud Hosting)
Wispbyte (Recommended Free Tier)
Create Account: wispbyte.com
Create Server: Select Python template
Upload Files: Use File Manager to upload project
Install Dependencies: pip install -r requirements.txt
Configure .env: Update with server IP and port
Start: Use provided run.py launcher
Oracle Cloud (Always Free)
bash
123456789101112
📦 Project Structure
1234567891011121314151617181920
🔧 Configuration
Game Settings (via /config)
Key
Default
Description
prep_time
300
Prep phase duration (seconds)
round_time
1800
Active phase duration (seconds)
jail_time_1
120
First offense jail time
jail_time_2
180
Second offense jail time
jail_time_3
240
Third+ offense jail time
respawn_cooldown
300
Time before respawn (seconds)
Pass Configuration
Key
Description
tot_pass_max_accounts
Max simultaneous TOT pass users (0 = unlimited)
tot_pass_min_credits
Minimum credits to purchase TOT pass
daily_pass_max_accounts
Max Daily pass users
all_pass_max_accounts
Max All-Access pass users
🛡️ Security
Admin Authentication: Session-based login with secure cookies
Rate Limiting: Prevents abuse of admin endpoints
Audit Logging: All admin actions recorded in event log
Input Validation: Sanitized user inputs prevent injection
Environment Variables: Sensitive data stored in .env (gitignored)
Tech Stack
Discord.py — Discord API integration
AIOHTTP — Async web server
SQLite3 — Lightweight database
Jinja2 — Template engine
UVLoop — High-performance event loop
Python 3.11+ — Core language
🤝 Contributing
Fork the repository
Create a feature branch (git checkout -b feature/AmazingFeature)
Commit your changes (git commit -m 'Add AmazingFeature')
Push to the branch (git push origin feature/AmazingFeature)
Open a Pull Request
📝 License
This project is licensed under the MIT License — see the LICENSE file for details.
🙏 Acknowledgments
Discord.py community for excellent documentation
Among Us for inspiration
Pterodactyl/Wispbyte for free hosting options
📞 Support
Discord Server: Join our community
Issues: GitHub Issues
Documentation: Wiki
<div align="center">

Made with ❤️ by Your Name
⭐ Star this repo if you find it useful!
</div>
