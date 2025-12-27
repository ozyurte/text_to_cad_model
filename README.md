Text-to-CAD Model generation in CATIA 3DEXPERIENCE

This repository contains a proof of concept for Text-to-CAD Model generation inside CATIA 3DEXPERIENCE, using Python automation (pywin32) and an agentic AI architecture.

The goal is to demonstrate that natural language can be translated into real, parametric, feature-based CAD models — generated live inside an active CATIA V6 session.

This is not a macro replay, template instantiation, or recorded script.
All geometry is constructed dynamically at runtime through the CATIA automation API.

What the demo shows

The accompanying video demonstrates the full workflow end-to-end:

A Python-based AI agent is executed

A natural-language prompt is provided (e.g. “Create a cylindrical flange…”)

CATIA generates the 3D CAD model live, inside the running session

During execution, the agent:

Creates sketches on valid supports (planes or solid faces)

Maintains correct parent–child relationships in the feature tree

Resolves feature direction and solid continuity

Updates the model directly within the CATIA V6 kernel

The result is a fully parametric CAD model, identical in structure to a manually created part.

Why a simple example?

The demonstrated part (a stepped cylindrical flange) is intentionally simple.

It serves the same purpose as a Hello World example in software development:
to validate that the entire pipeline — language interpretation, CAD intent resolution, feature creation, and kernel execution — is wired correctly and behaves deterministically.

Once this foundation is stable, the same logic can scale to real engineering workflows.

Potential extensions

The architecture demonstrated here can be extended to more advanced use cases, such as:

Automated fixture or support design based on part geometry

Early-stage routing for piping or cabling

Parametric assemblies configured via natural language

Rule-based or constraint-aware CAD generation

The focus of this repository is the core Text-to-CAD execution loop, not a finished product.

Data privacy and AI usage

For production-critical workflows (patents, R&D, proprietary designs), local LLMs are mandatory.
Sensitive CAD data must never leave the organization.

Cloud-based models (e.g. DeepSeek, OpenAI) should only be used for:

Research

General logic

Fully anonymized inputs

They must never be used with real corporate CAD data.

Status

Proof of concept

Research / experimental

Not production-ready

The repository is intended for exploration, discussion, and architectural validation.

License

MIT License
