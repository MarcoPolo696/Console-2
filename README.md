# 🤖 Discord Bot & Web Dashboard Ecosystem

A fully featured, dual-engine Discord bot and interactive web server ecosystem built using Python (`discord.py` and `Flask`). This project combines a digital product storefront, an advanced server economy system, moderation tools, private support tickets, and a responsive Tailwind CSS web dashboard synced dynamically via local JSON storage.

---

## 🌟 Key Features

### 🌐 Web Dashboard (`Flask`)
* **Live Store Showcase:** Public display of items, prices, and digital product types.
* **Dynamic User Dashboard:** Logged-in users can view their real-time Discord coin balance and active order history.
* **Secure Session Control:** Backend user session validation linked seamlessly with Discord accounts.

### 💰 Economy System
* **Daily Rewards:** Time-locked `$daily` / `/daily` coin collection command.
* **Wallet System:** Check current coin balances at any time.
* **Admin Controls:** Whitelisted staff can award or deduct coins dynamically.

### 📦 Store & Ticket Engine
* **Order Placement:** Create digital product orders directly from Discord with option tags.
* **Thread Tickets:** Create automatic, individual private support channels utilizing Discord's native thread architecture.
* **Cross-Server Links:** Establish secure, administrative cross-server pathways between separate guilds using Guild and Channel IDs.

---

## 📋 Prerequisites & Requirements

Before deploying the ecosystem, ensure you meet the following requirements:

1. **Python 3.8+** installed on your host system.
2. **Library Dependencies:** Install the external packages via pip:
   ```bash
   pip install -r requirements.txt
