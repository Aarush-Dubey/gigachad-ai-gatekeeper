import os
import itertools
from typing import List, Optional

class KeyManager:
    """
    Manages API keys in a Round Robin (Robin Hood?) fashion.
    Designed to rotate through a list of keys to distribute load.
    """
    def __init__(self, keys: List[str]):
        self.keys = keys
        # Cycle allows infinite rotation
        self._iterator = itertools.cycle(keys) if keys else None

    def get_next_key(self) -> Optional[str]:
        """Returns the next API key in the rotation."""
        if not self._iterator:
            return None
        return next(self._iterator)

    @classmethod
    def from_env(cls, env_var_name: str = "GROQ_API_KEYS", fallback: str = "GROQ_API_KEY"):
        """
        Initializes the KeyManager from environment variables.
        Expects a comma-separated list of keys in `env_var_name` (default: GROQ_API_KEYS).
        Falls back to a single key in `fallback` (default: GROQ_API_KEY) if the list is empty.
        """
        # Try finding the list variable
        keys_str = os.getenv(env_var_name)
        keys = []
        if keys_str:
            # Split by comma and strip whitespace
            keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        
        # If no list found, try the fallback single key
        if not keys:
            single_key = os.getenv(fallback)
            if single_key:
                keys = [single_key]
                
        # Also look for numbered keys like GROQ_API_KEY_1, GROQ_API_KEY_2, etc.
        # This is often safer for .env files than long comma strings
        i = 1
        while True:
            numbered_key = os.getenv(f"{fallback}_{i}")
            if numbered_key:
                if numbered_key not in keys: # Avoid duplicates if fallback was one of them
                    keys.append(numbered_key)
                i += 1
            else:
                break
        
        return cls(keys)

    def get_key_count(self) -> int:
        return len(self.keys)
