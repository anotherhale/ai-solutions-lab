"""Provider ports for chat and embeddings.

Domain packages do not import a vendor SDK. The OpenAI client stays in
``ai.infrastructure`` and is constructed only when configuration selects it.
"""
