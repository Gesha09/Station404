import sqlite3
import uuid
from datetime import datetime
from shared.config import settings

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # ============ 1. PLAYERS TABLE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                discord_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                pocket_credits INTEGER DEFAULT 100,
                vault_bonds INTEGER DEFAULT 0,
                profile_url TEXT UNIQUE NOT NULL,
                registered_at TEXT NOT NULL,
                registration_dm_id TEXT,
                is_on_duty INTEGER DEFAULT 0,
                last_active_at TEXT NOT NULL,
                jail_release_at TEXT,
                jail_offense_count INTEGER DEFAULT 0,
                is_alive INTEGER DEFAULT 1,
                respawn_at TEXT,
                current_room TEXT DEFAULT 'cafeteria',
                last_move_at TEXT,
                last_search_at TEXT,
                spawn_protected_until TEXT,
                first_action_taken INTEGER DEFAULT 0,
                has_shield INTEGER DEFAULT 0,
                has_rob_proof INTEGER DEFAULT 0,
                has_stealth_rob INTEGER DEFAULT 0,
                has_bank_pass INTEGER DEFAULT 0,
                last_rob_at TEXT,
                last_task_at TEXT,
                last_kill_at TEXT,
                mystery_boxes_opened INTEGER DEFAULT 0,
                action_steps_used INTEGER DEFAULT 0
            )
        """)
        
        # ============ 2. ROUNDS TABLE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rounds (
                id TEXT PRIMARY KEY,
                round_number INTEGER UNIQUE NOT NULL,
                status TEXT DEFAULT 'idle',
                started_at TEXT,
                ended_at TEXT,
                imposter_ids TEXT DEFAULT '[]',
                winner_id TEXT,
                win_type TEXT
            )
        """)
        
        # ============ 3. ROUND EARNINGS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS round_earnings (
                id TEXT PRIMARY KEY,
                round_id TEXT NOT NULL,
                player_id TEXT NOT NULL,
                discord_id TEXT NOT NULL,
                username TEXT NOT NULL,
                pocket_credits_earned INTEGER DEFAULT 0,
                pocket_credits_stolen INTEGER DEFAULT 0,
                UNIQUE(round_id, player_id)
            )
        """)
        
        # ============ 4. GAME CONFIG ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                description TEXT
            )
        """)
        
        defaults = [
            ("prep_phase_duration", "60", "Prep phase duration in seconds"),
            ("round_duration", "600", "Total round duration in seconds"),
            ("imposters_count", "1", "Number of imposters at any time"),
            ("imposter_rotation_interval", "180", "Seconds between imposter rotations"),
            ("witness_timer", "180", "Witness decision timer in seconds"),
            ("jail_time_1", "120", "First offense jail time in seconds"),
            ("jail_time_2", "180", "Second offense jail time in seconds"),
            ("jail_time_3", "240", "Third+ offense jail time in seconds"),
            ("daily_tax", "50", "Daily participation tax"),
            ("robbery_cut", "30", "Percentage stolen during robbery"),
            ("kill_steal", "100", "Percentage stolen on kill"),
            ("task_reward_min", "50", "Minimum task reward"),
            ("task_reward_max", "200", "Maximum task reward"),
            ("move_cooldown", "90", "Movement cooldown in seconds"),
            ("search_cooldown", "30", "Search cooldown in seconds"),
            ("rob_cooldown", "60", "Robbery cooldown in seconds"),
            ("task_cooldown", "45", "Task completion cooldown in seconds"),
            ("kill_cooldown", "120", "Imposter kill cooldown in seconds"),
            ("kill_cooldown_final", "30", "Kill cooldown during Final Phase"),
            ("loot_spawn_interval", "180", "Seconds between loot spawns"),
            ("loot_amount_min", "50", "Minimum loot spawn amount"),
            ("loot_amount_max", "200", "Maximum loot spawn amount"),
            ("loot_despawn_time", "300", "Seconds before unclaimed loot despawns"),
            ("final_phase_kill_pct", "50", "Percentage of crew killed to trigger Final Phase"),
            ("respawn_cooldown", "180", "Respawn cooldown in seconds"),
                        # Pass usage limits
            ("tot_pass_max_accounts", "1", "Max accounts that can use TOT pass"),
            ("daily_pass_max_accounts", "1", "Max accounts that can use Daily pass"),
            ("all_pass_max_accounts", "1", "Max accounts that can use All pass"),
            ("tot_pass_min_credits", "0", "Minimum credits required to buy TOT pass"),
            ("daily_pass_min_credits", "0", "Minimum credits required to buy Daily pass"),
            ("all_pass_min_credits", "0", "Minimum credits required to buy All pass"),
                        # Vault system
            ("vault_interest_rate", "5", "Interest rate per round won (percentage)"),
            ("vault_deposit_min", "10", "Minimum deposit amount"),
            ("vault_withdraw_min", "10", "Minimum withdraw amount"),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO game_config (key, value, description) VALUES (?, ?, ?)",
            defaults
        )
        
        # ============ 5. SHOP ITEMS TABLE (CREATE FIRST!) ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                id TEXT PRIMARY KEY,
                item_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price INTEGER NOT NULL,
                rarity TEXT DEFAULT 'common',
                item_type TEXT DEFAULT 'consumable',
                is_available INTEGER DEFAULT 1,
                stock_limit INTEGER,
                current_stock INTEGER,
                can_drop_in_loot INTEGER DEFAULT 0,
                loot_weight INTEGER DEFAULT 1,
                requires_approval INTEGER DEFAULT 0,
                is_approved INTEGER DEFAULT 0,
                effect_data TEXT DEFAULT '{}'
            )
        """)
        
        # ============ 6. NOW INSERT DEFAULT SHOP ITEMS ============
        shop_defaults = [
            # COMMON ITEMS (high loot weight = drop often)
            (str(uuid.uuid4()), "rob_proof", "Rob Proof Vest", "Blocks the next robbery attempt against you.", 300, "common", "consumable", 1, None, None, 1, 25, 0, 0, "{}"),
            (str(uuid.uuid4()), "mystery_box", "Mystery Box", "Open for random loot! May contain rare items.", 150, "common", "consumable", 1, None, None, 0, 0, 0, 0, "{}"),
            (str(uuid.uuid4()), "radar_ping", "Radar Ping", "Reveals who's in an adjacent room.", 200, "common", "consumable", 1, None, None, 1, 20, 0, 0, "{}"),
            
            # RARE ITEMS (medium loot weight)
            (str(uuid.uuid4()), "stealth_rob", "Stealth Rob Ticket", "Rob someone without any witnesses seeing.", 500, "rare", "consumable", 1, 5, 5, 1, 10, 0, 0, "{}"),
            (str(uuid.uuid4()), "bank_pass", "Bank Pass", "Deposit credits to vault during active round.", 350, "rare", "consumable", 1, None, None, 1, 8, 0, 0, "{}"),
            
            # EPIC ITEMS (low loot weight)
            (str(uuid.uuid4()), "shield_boost", "Shield Boost", "Survive one imposter kill attempt.", 400, "epic", "consumable", 1, 3, 3, 1, 4, 0, 0, "{}"),
            
            # LEGENDARY ITEMS (very low loot weight)
            (str(uuid.uuid4()), "tot_pass", "Limited TOT Pass", "Exclusive pass. Requires admin approval.", 1000, "legendary", "special", 1, None, None, 1, 1, 1, 0, "{}"),
            (str(uuid.uuid4()), "daily_pass", "Limited Daily Pass", "Exclusive pass. Requires admin approval.", 800, "legendary", "special", 1, None, None, 1, 1, 1, 0, "{}"),
            (str(uuid.uuid4()), "all_pass", "All-Access Pass", "Exclusive pass. Requires admin approval.", 1500, "legendary", "special", 1, None, None, 0, 0, 1, 0, "{}"),
        ]
        cursor.executemany(
            """INSERT OR IGNORE INTO shop_items 
               (id, item_id, name, description, price, rarity, item_type, is_available, 
                stock_limit, current_stock, can_drop_in_loot, loot_weight, requires_approval, is_approved, effect_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            shop_defaults
        )
        
        # ============ 7. PLAYER INVENTORY ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_inventory (
                id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                acquired_at TEXT NOT NULL,
                UNIQUE(player_id, item_id)
            )
        """)
        
        # ============ 8. APPROVAL REQUESTS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                discord_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                approval_code TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT,
                rejection_reason TEXT,
                usage_limit INTEGER DEFAULT 1,
                usage_remaining INTEGER DEFAULT 1,
                pinned_message_id TEXT
            )
        """)
        
        # ============ 9. PLAYER STATS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                id TEXT PRIMARY KEY,
                player_id TEXT UNIQUE NOT NULL,
                rounds_played INTEGER DEFAULT 0,
                rounds_won INTEGER DEFAULT 0,
                times_imposter INTEGER DEFAULT 0,
                times_eliminated INTEGER DEFAULT 0,
                times_jailed INTEGER DEFAULT 0,
                successful_robberies INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_stolen INTEGER DEFAULT 0
            )
        """)
        
        # ============ 10. GAME STATE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # ============ 11. EVENT LOG (Audit Trail) ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_id TEXT,
                actor_name TEXT,
                target_id TEXT,
                target_name TEXT,
                details TEXT DEFAULT '{}',
                round_id TEXT
            )
        """)
        
        # ============ 12. ADMIN SESSIONS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                ip_address TEXT
            )
        """)

                # ============ 13. VAULT TRANSACTIONS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vault_transactions (
                id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                discord_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # ============ 14. ACTIVE EFFECTS ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_effects (
                id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                uses_remaining INTEGER DEFAULT 1,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(player_id, effect_type)
            )
        """)
        
        # ============ 15. TRADE HISTORY ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                receiver_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        
        self.conn.commit()
        print("✅ Database tables created!")
    
    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor
    
    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    def close(self):
        self.conn.close()

db = Database()