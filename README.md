# 🚀 Station 404

<div align="center">

![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![AIOHTTP](https://img.shields.io/badge/AIOHTTP-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)

**A Next-Generation Discord Bot with Integrated Web Dashboard**  
*Where Strategy Meets Social Deduction*

[Features](#-features) • [Gameplay](#-gameplay) • [Commands](#-commands) • [Installation](#-installation) • [Dashboard](#-web-dashboard)

</div>

---

## 🌌 Overview

**Station 404** is a sophisticated Discord bot that transforms your server into an immersive social deduction game arena. Inspired by classics like *Among Us*, it combines strategic gameplay, economy management, and a powerful web-based administration panel — all seamlessly integrated.

Whether you're commanding a round as the imposter or building your fortune through the shop system, Station 404 delivers a rich, interactive experience with enterprise-grade reliability.

---

## ✨ Features

### 🎮 Core Gameplay
- **🎭 Imposter System** — Secretly assigned roles with phase-based rotations
- **👁️ Witness Mechanics** — Players who witness crimes can report or stay silent
- **⚔️ Combat & Robbery** — Strategic elimination and theft mechanics with stealth options
- **🔄 Dynamic Rounds** — Prep → Active → End phases with automatic management
- **📊 Live Statistics** — Real-time tracking of kills, robberies, and earnings

### 🛒 Advanced Economy
- **💰 Dual Currency System** — Pocket Credits (spendable) & Vault Bonds (secure)
- **🎫 Usage-Based Passes** — TOT, Daily, and All-Access passes with configurable limits
- **📦 Mystery Boxes** — Bulk-openable loot containers with weighted rarity tables
- **🔐 Approval System** — Admin-controlled item purchases with unique codes
- **🏪 Web Shop** — Full-featured online store synced with Discord

### 🎒 Inventory & Items
- **🛡️ Active Items** — Rob Proof, Shield Boost, Radar Ping, Stealth Rob, Bank Pass
- **🎁 Loot Tables** — Customizable rarity distribution (Common/Rare/Epic/Legendary)
- **🧹 Auto-Cleanup** — Round-based DM management (preserves pinned messages)

### 🎛️ Admin Dashboard
- **📊 Real-Time Overview** — Live game state, player counts, and recent events
- **👥 Player Management** — Edit balances, jail/release, respawn, move rooms
- **🛒 Shop CRUD** — Create, edit, delete items without code changes
- **🔐 Approval Center** — Bulk approve/reject with Discord DM notifications
- **📜 Event Log** — Complete audit trail of all game actions
- **🎫 Pass Configuration** — Set min credits, max accounts per pass type

### 🤖 Bot Features
- **⚡ Slash Commands** — Modern Discord UI with auto-complete
- **🔔 Smart Notifications** — Tracked DMs that clean up after rounds
- **📌 Auto-Pin System** — Approval/rejection messages preserved permanently
- **📡 Web Integration** — Seamless Discord ↔ Web server communication
- **🔄 Auto-Restart** — Systemd services for 24/7 uptime

---

## 🎯 Gameplay

### The Cycle
```bash
┌─────────┐
│ Idle │
└────┬────┘
│ /startgame
▼
┌─────────┐
│ Prep │ (5 min)
└────┬────┘
│ Timer
▼
┌─────────┐
│ Active │ (30 min)
└────┬────┘
│ Timer / /forcestop
▼
┌─────────┐
│ End │ → Cleanup → Idle
└─────────┘
```

### Phase Breakdown

#### 1️⃣ Prep Phase (5 minutes)
- Players `/clockin` to join the round
- Imposter is secretly assigned
- Final preparations before chaos begins

#### 2️⃣ Active Phase (30 minutes)
- **Imposter**: Eliminate crew, steal credits, avoid detection
- **Crew**: Complete tasks, gather loot, survive
- **Witnesses**: Report crimes or stay silent
- **Robbers**: Strike when witnesses aren't looking

#### 3️⃣ Round End
- All DMs cleaned (except pinned approvals)
- Players respawned
- Stats recorded
- Ready for next round

### Key Mechanics

| Mechanic | Description |
|---|---|
| **🎭 Imposter Rotation** | New imposter chosen each phase; jailed imposters trigger emergency rotation |
| **👁️ Witness System** | Living players in the same room get DM buttons to REPORT or LOOK AWAY |
| **⚖️ Justice System** | Reported players jailed with escalating sentences (2/3/4 min) |
| **💀 Death & Respawn** | Killed players lose pocket credits; auto-respawn after cooldown |
| **💎 Economy** | Earn through tasks, loot, robbery; spend in shop or save in vault |

---

## 📜 Commands

### 👤 Registration & Profile

|Commands | Description
|---|---|
/register | <profile_url> Register your account |
/profile | View your profile |
/balance | Check your credits |


### 🎮 Gameplay

|Commands | Description
|---|---|
/clockin | Go on duty (join round)
/offduty | Go off duty
/move | <room> Move to a room
/search | Search your room for loot
/task | Complete a task for credits
/loot | Pick up loot in your room


### ⚔️ Combat

|Commands | Description
|---|---|
/rob @user | Rob another player
/votestop | Vote to stop the round


### 🛒 Shop & Inventory

|Commands | Description
|---|---|
/shop | Browse available items
/buy <item> [usage] | Purchase an item
/inventory | View your inventory
/use <item> [code] | Use an item from inventory


### Special Usage:

- **/buy mystery_box usage:5 Buy 5 mystery boxes**
- **/use mystery_box quantity:3 Open 3 boxes at once**
- **/buy tot_pass usage:10 Buy TOT pass with 10 uses**
- **/use tot_pass code:ABC123 Use approved pass**

### 👑 Admin Commands

|Commands | Description
|---|---|
/startgame | Start a new round
/forcestop | Force end current round
/config | view View configuration
/config set [key] [value] | Update config
/approvals | View pending approvals
/approve [code] | Approve an item
/reject [code] | Reject an item

## 🌐 Web Dashboard

Access your server's control panel at: `http://YOUR_SERVER_IP:PORT`

### Dashboard Sections

#### 📊 Overview
- **Current round status & phase**
- **Player count (total/on duty)**
- **Live event feed**
- **Game statistics**

#### 👥 Players
- **Searchable player list**
- **Edit pocket credits & vault bonds**
- **Manual jail/release**
- **Room reassignment**
- **Kill/respawn controls**

#### 🛒 Shop Management
- **Create/edit/delete items**
- **Set prices, rarity, stock limits**
- **Configure loot weights**
- **Toggle approval requirements**

#### 🔐 Approvals
- Pending requests with player names
- One-click approve/reject
- Auto-DM notifications
- Approval history

#### 🎫 Pass Settings
- **Configure max accounts per pass**
- **Set minimum credit requirements**
- **Toggle pass availability**
- **Real-time usage tracking**

#### 📜 Event Log
- **Filterable by event type**
- **Full audit trail**
- **Exportable data**
- **Timestamp & actor tracking**

## 🛠️ Installation

### Prerequisites
- **Python 3.11+**
- **Discord Bot Token ([Get it here](https://discord.com/developers/applications))**
- **SQLite3 (included with Python)**
- **Git**

### Quick Start

```bash

# Clone repository
git clone https://github.com/YOUR_USERNAME/station404.git
cd station404

# Create virtual environment
python -m venv venv

# Activate environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Discord token and settings

# Run the bot
python run.py
```

### Environment Variables (.env)
```bash
# Discord Bot
DISCORD_TOKEN=your_discord_bot_token_here

# Admin
ADMIN_ROLE_ID=your_admin_role_id_here
WEB_ADMIN_SECRET=your_admin_secret_here

# Web Server
WEB_URL=http://localhost:8000
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_PATH=station404.db
```

### 🚀 Deployment
- ***Wispbyte (Recommended Free Tier)
- ***Create Account: wispbyte.com***
- ***Create Server: Select Python template***
- ***Upload Files: Use File Manager to upload project***
- ***Install Dependencies: pip install -r requirements.txt***
- ***Configure .env: Update with server IP and port***
- ***Start: Use provided run.py launcher***
- ***Oracle Cloud (Always Free)***

# Install dependencies
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv

# Setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service
sudo nano /etc/systemd/system/station404.service
# (See deployment guide in repo)

sudo systemctl enable station404
sudo systemctl start station404
```
#### 📦 Project Structure
```bash
station404/
├── bot/                    # Discord bot core
│   ├── main.py            # Bot initialization
│   ├── cogs/              # Command modules
│   │   ├── shop.py        # Shop & inventory
│   │   ├── combat.py      # Kill & rob commands
│   │   ├── gameplay.py    # Movement, tasks, loot
│   │   ├── admin.py       # Admin commands
│   │   └── info.py        # Help & info commands
│   └── core/              # Game logic
│       ├── game_manager.py    # Round management
│       ├── witness_system.py  # Crime reporting
│       ├── mystery_box.py     # Loot system
│       └── event_logger.py    # Audit trail
├── web/                   # Web dashboard
│   ├── main.py           # AIOHTTP server
│   ├── admin_auth.py     # Admin authentication
│   └── templates/        # HTML templates
├── database/             # Data layer
│   ├── db.py            # SQLite connection
│   └── repositories/    # Data access objects
├── shared/              # Shared utilities
│   └── config.py        # Environment config
├── run.py               # Combined launcher
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

#### 🔧 Configuration
***Game Settings (via /config)***

#### 🛡️ Security
- ***Admin Authentication — Session-based login with secure cookies***
- ***Rate Limiting — Prevents abuse of admin endpoints***
- ***Audit Logging — All admin actions recorded in event log***
- ***Input Validation — Sanitized user inputs prevent injection***
- ***Environment Variables — Sensitive data stored in .env (gitignored)***

#### 🧰 Tech Stack
- ***Discord.py — Discord API integration***
- ***AIOHTTP — Async web server***
- ***SQLite3 — Lightweight database***
- ***Jinja2 — Template engine***
- ***UVLoop — High-performance event loop***
- ***Python 3.11+ — Core language***

#### 🤝 Contributing

***Fork the repository
Create a feature branch (git checkout -b feature/AmazingFeature)
Commit your changes (git commit -m 'Add AmazingFeature')
Push to the branch (git push origin feature/AmazingFeature)
Open a Pull Request***

#### 📝 License
***This project is licensed under the - License — see the LICENSE file for details.***

#### 🙏 Acknowledgments
***Discord.py community for excellent documentation
Among Us for inspiration
Pterodactyl/Wispbyte for free hosting options***

#### 📞 Support
***Issues: GitHub Issues
Discord: Join our community***
<div align="center">

***Made with ❤️ by Gesha
⭐ Star this repo if you find it useful!***

---
