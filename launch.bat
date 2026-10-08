@echo off
title Claude Desktop Profile Launcher
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_user_n.ps1" %*
