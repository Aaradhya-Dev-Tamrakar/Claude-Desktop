@echo off
title Close All Claude Instances
pwsh -NoProfile -ExecutionPolicy Bypass -Command "& { . '%~dp0launch_user_n.ps1' -TestHook; Close-AllClaudeInstances }"
pause
