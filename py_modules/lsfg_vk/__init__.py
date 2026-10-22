"""
Jedi LSFG-VK plugin package for Decky Loader.

This package installs MAKO Renderer and manages its Adaptive Frame Generation
profiles for Lossless Scaling, driven by a single target FPS per game.
"""

try:
    from .plugin import Plugin
    __all__ = ['Plugin']
except ImportError:
    __all__ = []
