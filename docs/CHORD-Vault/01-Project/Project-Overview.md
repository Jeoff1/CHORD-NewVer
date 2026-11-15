# Project Overview

## Goal

A church administration system that any Christian church can use: members,
giving, events, church services (weddings, burials, private Masses and
others), records, worship planning and ministries.

## Key constraint

The system is **generic** and **never asks for the church's denomination**
(adviser requirement). Churches differ in practice: one charges for weddings
and another doesn't; one offers private Masses and another has none. Those
differences are handled as settings each church edits, never as
denomination-specific features. See [[0001-configure-behavior-not-identity]].

## Relationship to the first CHORD

This is a second option alongside the original CHORD project
(`../CHORD`). The original was built around Tradition presets (Roman
Catholic, Alliance, Iglesia Ni Cristo), which require choosing a
denomination. This version replaces those with per-church settings. The two
projects use separate databases and share no data.
