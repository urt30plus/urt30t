"""
Shim for Python 3.13 and remove 3.12 warning

    discord.player.py:29:
    DeprecationWarning: 'audioop' is deprecated and slated for removal in Python 3.13

Since we don't use any voice commands this is a no-op module.
"""
