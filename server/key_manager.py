import os
import time
import random
from typing import List, Optional

class KeyManager:
    """
    Manages API keys with "The Hydra Protocol" (Smart Failover + Jailbreak).
    Tracks failed keys and prevents them from being reused until cooldown expires.
    """
    def __init__(self, keys: List[str]):
        self.keys = keys
        self.failed_keys = {} # Format: { 'key_string': timestamp_when_it_failed }
        self.cooldown_seconds = 60 # How long to ban a key (1 minute)

    def get_next_key(self) -> Optional[str]:
        """
        Returns a healthy key. 
        Automatically skips keys that are in 'Jail' (Cooldown).
        Forces a Jailbreak if ALL keys are down.
        """
        if not self.keys:
            return None

        current_time = time.time()
        
        # 1. PAROLE BOARD: Release keys that have served their time
        keys_to_free = [k for k, ban_time in self.failed_keys.items() 
                        if current_time - ban_time > self.cooldown_seconds]
        
        for k in keys_to_free:
            del self.failed_keys[k]

        # 2. SELECTION: Filter out currently jailed keys
        available_keys = [k for k in self.keys if k not in self.failed_keys]

        if not available_keys:
            # 🚨 SMART JAILBREAK: Check if oldest failure is ready for retry
            if not self.failed_keys:
                print("💀 CRITICAL: No keys available at all.")
                return None
                
            oldest_key, ban_time = min(self.failed_keys.items(), key=lambda x: x[1])
            time_in_jail = current_time - ban_time
            
            # If the oldest key has been banned for less than 10 seconds, DO NOT resurrect.
            # It will just fail again and cause an infinite loop.
            if time_in_jail < 10: 
                print(f"💀 SYSTEM OVERLOAD: All {len(self.keys)} keys exhausted. Oldest banned {time_in_jail:.1f}s ago. Waiting...")
                return None  # Main loop will handle this as 503 Service Unavailable

            print(f"⚡ FORCE RESURRECTION: Re-trying oldest key (banned {time_in_jail:.1f}s ago).")
            del self.failed_keys[oldest_key]
            return oldest_key

        # 3. ROBIN HOOD: Random selection distributes load better than sequential
        return random.choice(available_keys)

    def report_failure(self, key: str):
        """Call this when a key gets a 429 (Rate Limit) or 401 (Auth Error)"""
        print(f"🚫 Key {key[:10]}... failed. Sending to jail for {self.cooldown_seconds}s.")
        self.failed_keys[key] = time.time()

    def get_key_count(self) -> int:
        return len(self.keys)

    @classmethod
    def from_env(cls, env_var_name: str = "GROQ_API_KEYS", fallback: str = "GROQ_API_KEY"):
        keys_str = os.getenv(env_var_name)
        keys = []
        if keys_str:
            keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        
        if not keys:
            single_key = os.getenv(fallback)
            if single_key:
                keys = [single_key]
                
        i = 1
        while True:
            # Try GROQ_API_KEY_N format first
            numbered_key = os.getenv(f"{fallback}_{i}")
            # Fallback to GROQ_KEY_N format
            if not numbered_key:
                numbered_key = os.getenv(f"GROQ_KEY_{i}")
            
            if numbered_key:
                if numbered_key not in keys:
                    keys.append(numbered_key)
                i += 1
            else:
                break
        
        print(f"🔥 KeyManager Loaded: {len(keys)} keys found.")
        return cls(keys)
