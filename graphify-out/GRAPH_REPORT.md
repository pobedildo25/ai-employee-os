# Graph Report - workspace  (2026-07-14)

## Corpus Check
- 533 files · ~125,210 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3865 nodes · 9105 edges · 273 communities (254 shown, 19 thin omitted)
- Extraction: 73% EXTRACTED · 27% INFERRED · 0% AMBIGUOUS · INFERRED: 2454 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c8472299`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- StrategyRequest
- LLMGateway
- CapabilityRegistry
- TelegramSessionManager
- PresentationPlanner
- QualityGate
- TelegramProductFlow
- TelegramAdapter
- TaskRepository
- ResponseParseError
- create_context_builder
- BusinessClientResolver
- AgentRuntime
- AgentState
- RevisionAgent
- Settings
- GraphBuilder
- Issue tracker: GitHub
- mock_gateway
- ObservabilityManager
- LearningRule
- Orchestrator
- ExecutionState
- PresentationDesigner
- MemoryManager
- QdrantSemanticMemory
- TaskPlan
- TelegramProgressMessenger
- WorkspaceManager
- Conversation
- ContextRequest
- build_executive_graph
- ResearchManager
- DocumentRepresentation
- RenderRequest
- ArtifactRepository
- ArtifactVersion
- InMemoryLongTermMemory
- build_e2e_registry
- Extractor
- MemoryItem
- create_capability_registry
- What You Must Do When Invoked
- InMemoryClientRepository
- KnowledgeItem
- Client
- build_revision_request_from_review
- WorkspaceService
- ProjectService
- BrandProfileManager
- ExecutionGraph
- ResearchSource
- DocumentAST
- ArtifactService
- DocumentRendererService
- KnowledgeManager
- ObservabilityProvider
- MockProvider
- APIKey
- file_factory.py
- AnalyticsDataset
- SecurityManager
- ClientService
- ArtifactRead
- ExecutionStore
- .__call__
- llm_fixtures.py
- build_readiness_payload
- InMemoryObservabilityProvider
- TaskQueueManager
- HTML Report Format
- E2EContextBuilderNode
- BackgroundWorker
- AnalyticsAnalyzer
- FastAPI
- BrandStyleExtractor
- BrandProfile
- build_execution_graph
- ExecutionContext
- .generate
- DocumentPipeline
- TimelineEvent
- logging.py
- AgentUnderstanding
- AnalyticsRequest
- FileProcessor
- WorkspaceSession
- ResearchResult
- deps.py
- ProjectRepository
- ASTNode
- PdfRenderer
- MemoryStore
- PlanStep
- models.py
- get_session_factory
- ClientIntelligenceSources
- KnowledgeMigrationService
- BackgroundTaskRecord
- AI Employee OS
- Diagnosing Bugs
- Find Skills
- AnalyticsResult
- CompositeAnalyticsDataProvider
- compute_all_metrics
- get_client_intelligence_manager
- PptxRenderer
- ClientIntelligenceAnalyzer
- parse_creation_response
- .process_bytes
- PostgresKnowledgeStore
- models.py
- .review
- ResearchType
- ResearchRequest
- Skill
- WorkspaceRepository
- Roadmap — AI Employee OS
- Test-Driven Development
- ClientRepository
- is_telegram_user_client
- TimelineRecorder
- test_api_v1.py
- ArtifactStatus
- ObservabilityLogger
- models.py
- BackgroundTask
- read_file_bytes
- test_client_intelligence.py
- ClientProfile
- .extract
- MetricsCollector
- BackgroundTaskNode
- ingest_archive
- Project Context — AI Employee OS
- Ask Matt
- TelegramFlowMode
- AnalyticsDataProvider
- executions.py
- security.py
- extract_business_subject
- builder.py
- KnowledgeMigrationNode
- SQLAlchemyProjectRepository
- .__init__
- release_on_server.py
- TaskQueueRepository
- test_workspace.py
- Architecture — AI Employee OS
- graphify reference: extra exports and benchmark
- SKILL.md
- .collect
- ArtifactVersionRepository
- workspace.py
- build_brand_profile
- ClientIntelligenceManager
- SQLAlchemyClientRepository
- SecurityMiddleware
- Process
- .enrich_with_llm
- intelligence.py
- .__call__
- SQLAlchemyArtifactVersionRepository
- RetryPolicy
- WorkspaceContextProvider
- Architecture Decision Records (ADR)
- .interpret
- create_artifact
- run_execution
- learning.py
- parse_revision_response
- prepare_knowledge_memory_items
- ResearchManagerInterface
- ResearchQueryBuilder
- SecretsManager
- InMemoryTaskQueueRepository
- Core Components
- Document Intelligence
- graphify reference: query, path, explain
- env.py
- TelegramAdapterInterface
- models.py
- run_research
- ClientIntelligenceNode
- .analyze
- prepare_document_memory_items
- DocumentBuilder
- .extract
- KnowledgeContextProvider
- .execute
- AuditRetentionPolicy
- Cross-Cutting Concerns
- orchestration_parser.py
- AuditLogger
- competitor_analysis.py
- marketing_plan.py
- positioning.py
- backup_postgres.py
- restore_postgres.py
- Пользовательские сценарии
- hitl-loop.template.sh
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native AGENTS.md integration
- graphify reference: incremental update and cluster-only
- Local setup
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- is_contextual_revision_message
- layout_rules.py
- provision_production.sh
- extraction-spec.md
- __init__.py
- __init__.py
- dependencies.py
- __init__.py
- __init__.py
- prompt.py
- __init__.py
- api_key_provider.py
- entrypoint.sh

## God Nodes (most connected - your core abstractions)
1. `CapabilityRegistry` - 86 edges
2. `LLMGateway` - 82 edges
3. `Settings` - 70 edges
4. `TelegramProductFlow` - 61 edges
5. `AgentRuntime` - 61 edges
6. `WorkspaceService` - 61 edges
7. `MemoryItem` - 60 edges
8. `AgentState` - 59 edges
9. `TelegramSessionManager` - 56 edges
10. `ArtifactService` - 54 edges

## Surprising Connections (you probably didn't know these)
- `test_brand_profile_creation()` --calls--> `BrandProfile`  [INFERRED]
  backend/tests/test_brand_style.py → backend/app/brand_style/models.py
- `test_build_brand_profile_from_raw_style()` --calls--> `build_brand_profile()`  [INFERRED]
  backend/tests/test_brand_style.py → backend/app/brand_style/rules/style_rules.py
- `test_builder_and_manager()` --calls--> `ClientIntelligenceManager`  [INFERRED]
  backend/tests/test_client_intelligence.py → backend/app/client_intelligence/manager.py
- `test_profile_models()` --calls--> `ClientProfile`  [INFERRED]
  backend/tests/test_client_intelligence.py → backend/app/client_intelligence/models.py
- `lifespan()` --calls--> `close_postgres()`  [INFERRED]
  backend/app/main.py → backend/app/database/postgres.py

## Import Cycles
- None detected.

## Communities (273 total, 19 thin omitted)

### Community 0 - "StrategyRequest"
Cohesion: 0.06
Nodes (49): Any, Soft structural checks for strategy outputs — no business decisions., StrategyAnalyzer, normalize_framework(), section_hints_for(), empty_swot(), normalize_swot(), Any (+41 more)

### Community 1 - "LLMGateway"
Cohesion: 0.06
Nodes (48): LLMAuthenticationError, LLMConfigurationError, LLMError, LLMModelNotAvailableError, LLMProviderError, LLMRateLimitError, Exception, Raised when LLM Gateway is misconfigured. (+40 more)

### Community 2 - "CapabilityRegistry"
Cohesion: 0.05
Nodes (41): BaseSkill, Any, Base skill with stub execution — no business logic., AnalysisSkill, Analysis-related capabilities., ClientIntelligenceSkill, Any, Aggregates what the system knows about a client for downstream agents. (+33 more)

### Community 3 - "TelegramSessionManager"
Cohesion: 0.13
Nodes (45): Transport-only state for multi-turn Telegram UX. No business rules., TelegramConversationStore, InMemoryTelegramSender, Test/double sender that records outbound messages., Links telegram_user_id → Workspace → Session via existing WorkspaceManager., TelegramSessionManager, test_telegram_full_flow_with_progress_approval_and_delivery(), test_llm_timeout_retries_then_friendly_error() (+37 more)

### Community 4 - "PresentationPlanner"
Cohesion: 0.07
Nodes (38): PresentationAnalyzer, Storytelling / structure checks — no fixed business templates., Any, PresentationDesignerInterface, PresentationPlannerInterface, ABC, Any, ContentBlock (+30 more)

### Community 5 - "QualityGate"
Cohesion: 0.07
Nodes (33): ContentCheck, Any, Universal check: result exists and aligns with stated goal., Any, Universal check: document AST integrity when present., StructureCheck, Any, Universal check: brand profile presence and basic style metadata. (+25 more)

### Community 6 - "TelegramProductFlow"
Cohesion: 0.11
Nodes (25): TelegramConversationState, Any, Telegram product UX over existing runtime, orchestrator, and revision nodes., Find-or-create the business client this task is for and route the run to it., _safe_error_reason(), TelegramProductFlow, approval_keyboard(), Any (+17 more)

### Community 7 - "TelegramAdapter"
Cohesion: 0.08
Nodes (29): Any, Thin bot facade — holds adapter; no business decisions., Telegram transport adapter over existing AgentRuntime + Workspace., TelegramAdapter, TelegramBot, Any, Dispatches Telegram updates to product flow handlers., TelegramDispatcher (+21 more)

### Community 8 - "TaskRepository"
Cohesion: 0.09
Nodes (21): get_task_service(), create_task(), delete_task(), get_task(), list_background_tasks(), list_tasks(), UUID, update_task() (+13 more)

### Community 9 - "ResponseParseError"
Cohesion: 0.07
Nodes (29): extract_json_content(), parse_executive_response(), Exception, Raised when LLM response cannot be parsed into a valid schema., ResponseParseError, parse_knowledge_response(), UUID, LearningExtractor (+21 more)

### Community 10 - "create_context_builder"
Cohesion: 0.08
Nodes (29): ClientIntelligenceContextProvider, Injects aggregated client intelligence after knowledge, before learning., ContextBuilder, ContextBuilderNode, create_context_builder(), LangGraph node: builds ExecutionContext before Executive Agent., Collects and assembles execution context from independent providers., ArtifactContextProvider (+21 more)

### Community 11 - "BusinessClientResolver"
Cohesion: 0.11
Nodes (22): BusinessClientResolver, Resolve (find or create) the business client a chat task belongs to.  When a use, ResolvedBusinessClient, FakeGateway, FakeLLMResponse, InMemoryClientRepository, InMemoryProjectRepository, _make_flow() (+14 more)

### Community 12 - "AgentRuntime"
Cohesion: 0.08
Nodes (27): CheckpointManager, InMemoryCheckpointManager, ABC, Any, Interface for saving and restoring workflow execution state., Remove persisted state. Returns True if an entry was removed., Return LangGraph-compatible checkpointer instance., In-memory checkpoint store for development and testing. (+19 more)

### Community 13 - "AgentState"
Cohesion: 0.07
Nodes (27): Persist workflow state for the given execution., Load persisted workflow state, or None if not found., Route after quality gate: revise once automatically, otherwise end., Connect full pipeline with optional one-shot revision loop., route_after_executive(), route_after_quality(), wire_executive_workflow(), Any (+19 more)

### Community 14 - "RevisionAgent"
Cohesion: 0.09
Nodes (28): Any, Exception, Raised when revision planning fails., RevisionAgent, RevisionAgentError, ABC, Any, Apply revision based on quality feedback. (+20 more)

### Community 15 - "Settings"
Cohesion: 0.08
Nodes (21): get_llm_gateway(), get_storage(), build_telegram_bot(), AsyncSession, Production Telegram wiring using existing adapters (no new transport layer)., Build a Telegram bot bound to one DB session (commit per update)., get_settings(), Settings (+13 more)

### Community 16 - "GraphBuilder"
Cohesion: 0.09
Nodes (31): AgentRuntimeError, GraphBuildError, Exception, Base exception for agent runtime errors., Raised when graph construction or compilation fails., GraphBuilder, Any, CompiledStateGraph (+23 more)

### Community 17 - "Issue tracker: GitHub"
Cohesion: 0.06
Nodes (30): Before exploring, read these, Domain Docs, File structure, Flag ADR conflicts, Use the glossary's vocabulary, Conventions, Issue tracker: GitHub, Pull requests as a triage surface (+22 more)

### Community 18 - "mock_gateway"
Cohesion: 0.13
Nodes (25): LearningDetector, Detects whether an event carries a durable learning signal., LearningManager, Any, UUID, Persists durable behavior rules — not model fine-tuning., InMemoryLearningStore, test_learning_rule_persists_and_reaches_context_builder() (+17 more)

### Community 19 - "ObservabilityManager"
Cohesion: 0.09
Nodes (16): get_observability_manager(), get_metrics(), get_trace(), list_traces(), ObservabilityManager, Any, Facade for traces, timeline, metrics, and export — no agent decisions., ExecutionTrace (+8 more)

### Community 20 - "LearningRule"
Cohesion: 0.12
Nodes (13): LearningStore, ABC, UUID, LearningRule, UUID, PostgresLearningStore, AsyncSession, UUID (+5 more)

### Community 21 - "Orchestrator"
Cohesion: 0.09
Nodes (17): Any, UUID, Send rendered artifacts to Telegram using existing ArtifactService + storage., TelegramArtifactDelivery, _to_uuid(), create_telegram_adapter(), create_telegram_bot(), Wire Telegram transport to existing runtime/workspace. No new singletons. (+9 more)

### Community 22 - "ExecutionState"
Cohesion: 0.10
Nodes (14): resume_execution(), OrchestratorInterface, ABC, Pause a running execution., Resume a paused execution., Cancel a running or paused execution., ExecutionState, can_cancel() (+6 more)

### Community 23 - "PresentationDesigner"
Cohesion: 0.09
Nodes (19): DocumentCreationNode, _log_node(), Any, UUID, Planner → PresentationDesign → DocumentRender path (AST only here)., _to_uuid(), _wants_presentation(), should_create_document() (+11 more)

### Community 24 - "MemoryManager"
Cohesion: 0.11
Nodes (24): _dedupe_and_limit(), MemoryError, MemoryManager, MemoryRetentionError, Exception, UUID, Base memory system error., Raised when an item fails retention policy checks. (+16 more)

### Community 25 - "QdrantSemanticMemory"
Cohesion: 0.10
Nodes (16): _build_filter(), InMemorySemanticMemory, QdrantClient, UUID, QdrantSemanticMemory, In-memory semantic memory for tests., Deterministic stub embedding for development — not a real embedding model., Qdrant-backed semantic memory with stub embeddings. (+8 more)

### Community 26 - "TaskPlan"
Cohesion: 0.15
Nodes (16): Any, Execute an ExecutionGraph and return updated state and task execution., Any, ApprovalState, ExecutionLogEntry, BaseModel, TaskExecution, TaskPlan (+8 more)

### Community 27 - "TelegramProgressMessenger"
Cohesion: 0.11
Nodes (9): _extract_message_id(), Any, Edits a single Telegram message for execution progress with throttling., TelegramProgressMessenger, HttpTelegramSender, ABC, Any, Sends messages to Telegram — no text generation. (+1 more)

### Community 28 - "WorkspaceManager"
Cohesion: 0.17
Nodes (7): Any, UUID, Infrastructure manager for AI Employee workspaces — no business logic., WorkspaceManager, Working space for an AI Employee — agent work state, not a user UI., Workspace, can_open_session()

### Community 29 - "Conversation"
Cohesion: 0.13
Nodes (14): BaseEntity, Base ORM model with UUID primary key and timestamps., ConversationRecord, Persisted AI Employee workspace state., Persisted session conversation buffer — does not replace Memory., WorkspaceRecord, Conversation, Session dialogue buffer. Does not replace Memory. (+6 more)

### Community 30 - "ContextRequest"
Cohesion: 0.08
Nodes (15): Any, ContextRequest, Input shared across context providers., Any, Any, Fetch a partial context fragment. Returns empty dict when not applicable., Any, Any (+7 more)

### Community 31 - "build_executive_graph"
Cohesion: 0.13
Nodes (21): build_executive_graph(), Build executive workflow with context, skills, and decision nodes., ExecutiveAgent, ExecutiveAgentError, Exception, Raised when executive agent analysis fails., Understands user intent and produces structured decisions via LLM Gateway., ChatResponseNode (+13 more)

### Community 32 - "ResearchManager"
Cohesion: 0.14
Nodes (19): get_context_builder(), get_research_manager(), get_research_manager_singleton(), Process-local research cache so GET /research/{id} can resolve prior runs., Runs research and keeps an in-memory result cache for API/context (not Knowledge, ResearchManager, Any, Search-oriented adapter — currently delegates to mock, ready for real search API (+11 more)

### Community 33 - "DocumentRepresentation"
Cohesion: 0.11
Nodes (15): Any, DocxStyleExtractor, Any, _rgb_to_hex(), PdfStyleExtractor, Any, ABC, Any (+7 more)

### Community 34 - "RenderRequest"
Cohesion: 0.13
Nodes (14): DocumentRenderer, ABC, Render document bytes from the request., Validate that the request can be rendered., OutputFormat, BaseModel, str, RenderRequest (+6 more)

### Community 35 - "ArtifactRepository"
Cohesion: 0.15
Nodes (7): Artifact, ArtifactRepository, ABC, UUID, AsyncSession, UUID, SQLAlchemyArtifactRepository

### Community 36 - "ArtifactVersion"
Cohesion: 0.14
Nodes (8): ArtifactVersion, artifact_service(), FakeArtifactRepository, FakeArtifactVersionRepository, ids(), InMemoryStorage, UUID, test_storage_upload_download_exists_delete()

### Community 37 - "InMemoryLongTermMemory"
Cohesion: 0.14
Nodes (12): Base, SQLAlchemy declarative base for all ORM models., _from_record(), InMemoryLongTermMemory, MemoryRecord, PostgresLongTermMemory, AsyncSession, UUID (+4 more)

### Community 38 - "build_e2e_registry"
Cohesion: 0.14
Nodes (15): DocumentCreator, DocumentASTGenerator, DocumentASTGeneratorError, Exception, Raised when AST generation fails., ASTValidationError, ASTValidator, Exception (+7 more)

### Community 39 - "Extractor"
Cohesion: 0.10
Nodes (9): DocxExtractor, ImageExtractor, PdfExtractor, PptxExtractor, TextExtractor, XlsxExtractor, Extractor, ABC (+1 more)

### Community 40 - "MemoryItem"
Cohesion: 0.17
Nodes (12): MemoryItem, _is_ephemeral(), Return True when a memory item is eligible for storage., should_persist(), InMemoryShortTermMemory, _matches_query(), UUID, Redis-backed short-term memory with TTL. (+4 more)

### Community 41 - "create_capability_registry"
Cohesion: 0.16
Nodes (20): TaskExecutor, ExecutorNode, parse_task_plan(), Exception, Raised when task planning fails., TaskPlanner, TaskPlannerError, build_planner_user_message() (+12 more)

### Community 42 - "What You Must Do When Invoked"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native AGENTS.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 43 - "InMemoryClientRepository"
Cohesion: 0.20
Nodes (14): UUID, Stable workspace client identity for a Telegram user (transport binding only)., Open or reuse Workspace/Session for the Telegram user. No memory writes., telegram_client_id(), telegram_user_client_metadata(), client_repository(), InMemoryClientRepository, UUID (+6 more)

### Community 44 - "KnowledgeItem"
Cohesion: 0.12
Nodes (8): UUID, Return knowledge fragments for Context Builder., KnowledgeItem, KnowledgeStore, ABC, UUID, Storage abstraction for client knowledge — Postgres now, Qdrant-ready later., UUID

### Community 45 - "Client"
Cohesion: 0.19
Nodes (14): Client, Project, client_id(), FakeArtifactRepository, FakeClientRepository, FakeProjectRepository, project_id(), UUID (+6 more)

### Community 46 - "build_revision_request_from_review"
Cohesion: 0.11
Nodes (19): prepare_revision_memory_items(), UUID, Prepare memory candidates from revision without auto-saving., _log_node(), Any, UUID, _to_uuid(), build_revision_request_from_review() (+11 more)

### Community 47 - "WorkspaceService"
Cohesion: 0.14
Nodes (16): LangGraph-ready node for workspace open — not wired into main workflow yet., WorkspaceNode, InMemoryWorkspaceRepository, In-memory workspace store for tests and local development., Any, UUID, Assembles workspace snapshots for context and runtime nodes., WorkspaceService (+8 more)

### Community 48 - "ProjectService"
Cohesion: 0.18
Nodes (12): create_project(), delete_project(), get_project(), list_projects(), UUID, update_project(), ProjectCreate, ProjectRead (+4 more)

### Community 49 - "BrandProfileManager"
Cohesion: 0.13
Nodes (15): BrandProfileManager, BrandProfileNotFoundError, _diff_dict(), prepare_brand_memory_items(), Any, Exception, UUID, In-memory brand profile store — foundation for memory-backed persistence. (+7 more)

### Community 50 - "ExecutionGraph"
Cohesion: 0.15
Nodes (9): DependencyResolver, Resolve node readiness from graph dependencies only., ExecutionGraph, ExecutionGraphNode, datetime, Schedule ready nodes for parallel execution and track statuses., Scheduler, test_dependency_resolver_ready_and_waiting() (+1 more)

### Community 51 - "ResearchSource"
Cohesion: 0.12
Nodes (12): CompanyAnalyzer, CompetitorAnalyzer, run_type_analyzers(), MarketAnalyzer, TrendAnalyzer, ResearchSource, _freshness(), datetime (+4 more)

### Community 52 - "DocumentAST"
Cohesion: 0.13
Nodes (15): _metrics_paragraphs(), result_to_document_ast(), _section(), DocumentAnalyzer, UUID, Builds universal document representation and AST from extracted content., build_document_ast(), _count_nodes() (+7 more)

### Community 53 - "ArtifactService"
Cohesion: 0.21
Nodes (11): create_artifact(), create_artifact_version(), get_artifact(), get_artifact_versions(), list_artifacts(), UploadFile, UUID, ArtifactUpdate (+3 more)

### Community 54 - "DocumentRendererService"
Cohesion: 0.15
Nodes (17): create_render_artifact_service(), DocumentRendererService, Routes render requests to format-specific renderers., Renders documents and persists them as generated artifacts., RenderArtifactService, DocumentRenderSkill, Renders documents from AST and brand profile into generated artifacts., brand_profile() (+9 more)

### Community 55 - "KnowledgeManager"
Cohesion: 0.21
Nodes (16): KnowledgeExtractor, KnowledgeManager, Client Knowledge Base — store, search, and context retrieval., InMemoryKnowledgeStore, In-memory knowledge store for tests and local development., knowledge_json(), settings(), test_context_builder_knowledge_integration() (+8 more)

### Community 56 - "ObservabilityProvider"
Cohesion: 0.12
Nodes (10): ConsoleExporter, Any, Writes observability export to console/log — observation only., JsonExporter, Any, Exports observability payload as JSON text., ObservabilityProvider, ABC (+2 more)

### Community 57 - "MockProvider"
Cohesion: 0.13
Nodes (9): Any, External research adapter — search/fetch/extract only, not a browser., ResearchProvider, MockProvider, Any, Deterministic mock sources — swappable for real APIs later., Any, Web fetch/extract adapter — mock-backed foundation for future HTTP providers. (+1 more)

### Community 58 - "APIKey"
Cohesion: 0.14
Nodes (7): ABC, UUID, SecurityStore, APIKey, AuditEvent, InMemorySecurityProvider, UUID

### Community 59 - "file_factory.py"
Cohesion: 0.17
Nodes (21): processor(), Path, tmp_docx(), tmp_pdf(), tmp_png(), tmp_pptx(), tmp_txt(), tmp_xlsx() (+13 more)

### Community 60 - "AnalyticsDataset"
Cohesion: 0.13
Nodes (9): DocumentAnalyzer, ClientAnalyzer, DocumentAnalyzer, PerformanceAnalyzer, ProjectAnalyzer, QualityAnalyzer, AnalyticsDataset, AnalyticsInsight (+1 more)

### Community 61 - "SecurityManager"
Cohesion: 0.16
Nodes (14): get_security_manager(), Request, UUID, Infrastructure security facade — no business decisions., SecurityManager, APIKeyInfo, SecurityPrincipal, manager() (+6 more)

### Community 62 - "ClientService"
Cohesion: 0.19
Nodes (12): create_client(), delete_client(), get_client(), list_clients(), UUID, update_client(), ClientCreate, ClientRead (+4 more)

### Community 63 - "ArtifactRead"
Cohesion: 0.13
Nodes (8): process_document(), UUID, ArtifactCreate, ArtifactRead, Any, FakeArtifactService, UUID, test_create_artifact()

### Community 64 - "ExecutionStore"
Cohesion: 0.13
Nodes (10): ExecutionRecord, ExecutionStore, get_execution_store_singleton(), Process-local store for orchestration lifecycle and API lookups., ExecutionValidationError, ExecutionValidator, _has_cycle(), Exception (+2 more)

### Community 65 - ".__call__"
Cohesion: 0.15
Nodes (18): prepare_quality_memory_items(), UUID, Prepare memory candidates from quality review without auto-saving., _log_node(), _merge_analytics_quality(), _merge_client_intelligence_quality(), _merge_presentation_quality(), _merge_research_quality() (+10 more)

### Community 66 - "llm_fixtures.py"
Cohesion: 0.15
Nodes (15): client_project_ids(), e2e_runtime_factory(), learning_manager(), settings(), brand_plan_steps(), e2e_settings(), marketing_plan_steps(), new_client_project_ids() (+7 more)

### Community 67 - "build_readiness_payload"
Cohesion: 0.15
Nodes (18): AsyncEngine, build_health_payload(), build_liveness_payload(), build_readiness_payload(), check_minio(), health(), Request, Response (+10 more)

### Community 68 - "InMemoryObservabilityProvider"
Cohesion: 0.11
Nodes (6): Limits in-memory observability retention — observation only., RetentionPolicy, InMemoryObservabilityProvider, Any, Process-local observability store — no external backends., manager()

### Community 69 - "TaskQueueManager"
Cohesion: 0.18
Nodes (9): Any, UUID, Internal task queue manager — no Celery/RabbitMQ/Kafka/Redis Queue., TaskQueueManager, test_background_task_model(), test_cancel(), test_enqueue_dequeue(), test_retry_policy_and_retry() (+1 more)

### Community 70 - "HTML Report Format"
Cohesion: 0.10
Nodes (18): Call-graph collapse, Candidate card, Cross-section (good for layered shallowness), Diagram patterns, Hand-built boxes-and-arrows (when Mermaid's layout fights you), Header, HTML Report Format, Mass diagram (good for "interface as wide as implementation") (+10 more)

### Community 71 - "E2EContextBuilderNode"
Cohesion: 0.15
Nodes (13): Resume existing graph nodes for Telegram revision without changing AgentRuntime., TelegramGraphContinuation, OrchestrationNode, _log_node(), PlannerNode, Any, QualityGateNode, RevisionNode (+5 more)

### Community 72 - "BackgroundWorker"
Cohesion: 0.14
Nodes (9): Any, Distributes queued tasks to workers. No cron — pull-based dispatch only., TaskScheduler, BackgroundWorker, In-process worker architecture — no separate processes on this stage., Dequeue one task and process it in-process. Architecture only — no daemon loop., test_scheduler_dispatch(), test_worker_process_next() (+1 more)

### Community 73 - "AnalyticsAnalyzer"
Cohesion: 0.18
Nodes (13): AnalyticsAnalyzer, Combines domain analyzers with optional LLM interpretation., AnalyticsSkill, Any, Analytics & reporting over existing system sources (AST for Document/Presentatio, FakeClientService, _sample_dataset(), settings() (+5 more)

### Community 74 - "FastAPI"
Cohesion: 0.15
Nodes (12): create_app(), lifespan(), RateLimiter, In-memory rate limiter — no Redis., test_health_and_ready_endpoints(), client(), AsyncClient, test_liveness_health() (+4 more)

### Community 75 - "BrandStyleExtractor"
Cohesion: 0.15
Nodes (15): BrandStyleExtractor, Routes style extraction to format-specific extractors., BrandStyleAnalysisSkill, Extracts brand style from documents and returns BrandProfile data., brand_extractor(), pipeline(), Path, test_brand_profile_creation() (+7 more)

### Community 76 - "BrandProfile"
Cohesion: 0.26
Nodes (6): BrandProfile, BaseModel, Any, Applies brand profile styles to document elements., StyleApplier, test_style_applier_uses_brand_profile()

### Community 77 - "build_execution_graph"
Cohesion: 0.20
Nodes (15): build_execution_graph(), Convert a TaskPlan into a dynamic ExecutionGraph., ProgressTracker, Compute progress from completed graph nodes., orchestrator(), sample_plan(), settings(), test_build_execution_graph() (+7 more)

### Community 78 - "ExecutionContext"
Cohesion: 0.15
Nodes (15): ExecutionContext, Any, BaseModel, Unified execution context for the Executive Agent., build_prioritized_context(), _has_value(), Any, Return context fields ordered by priority for downstream agents. (+7 more)

### Community 79 - ".generate"
Cohesion: 0.16
Nodes (11): DocumentCreatorInterface, ABC, Create document AST from user intent., _collect_headings(), prepare_document_creation_memory_items(), UUID, Prepare memory candidates from document creation without auto-saving., DocumentCreationRequest (+3 more)

### Community 80 - "DocumentPipeline"
Cohesion: 0.19
Nodes (16): DocumentPipeline, Upload → Detect → Extract → Analyze → Build AST → Store Representation., DocumentAnalysisSkill, Provides document analysis capability — understanding and structure only., test_broken_artifact_validation(), analyzer(), pipeline(), DocumentAnalyzer (+8 more)

### Community 81 - "TimelineEvent"
Cohesion: 0.16
Nodes (9): ExecutionTimeline, BaseModel, Enum, str, TimelineEvent, TimelineEventStatus, TraceStatus, Assembles and updates ExecutionTimeline records. (+1 more)

### Community 82 - "logging.py"
Cohesion: 0.14
Nodes (9): setup_logging(), TraceIdFilter, _log_node(), _log_node(), Any, Resolves AgentUnderstanding.required_capabilities against the registry., SkillResolverNode, test_skill_resolver_node() (+1 more)

### Community 83 - "AgentUnderstanding"
Cohesion: 0.18
Nodes (11): AgentDecision, DecisionType, BaseModel, Enum, str, AgentUnderstanding, ExecutiveAgentResult, BaseModel (+3 more)

### Community 84 - "AnalyticsRequest"
Cohesion: 0.19
Nodes (14): AnalyticsRequest, AnalyticsType, DateRange, BaseModel, Enum, str, Any, AnalyticsRunRequest (+6 more)

### Community 85 - "FileProcessor"
Cohesion: 0.17
Nodes (9): get_file_processing_service(), DocumentAnalyzer, FileProcessor, FileProcessingService, UUID, test_docx_with_tables_pipeline(), test_large_pdf_pipeline(), test_artifact_metadata_update_after_processing() (+1 more)

### Community 86 - "WorkspaceSession"
Cohesion: 0.17
Nodes (10): Persisted workspace session., WorkspaceSessionRecord, BaseModel, Enum, str, WorkspaceSession, WorkspaceSessionStatus, can_attach_conversation() (+2 more)

### Community 87 - "ResearchResult"
Cohesion: 0.18
Nodes (8): UUID, _as_uuid(), prepare_research_memory_items(), UUID, Prepare memory/knowledge candidates — never auto-saves., ResearchResult, ResearchValidator, test_quality_checks()

### Community 88 - "deps.py"
Cohesion: 0.22
Nodes (15): get_artifact_repository(), get_artifact_version_repository(), get_capability_registry(), get_client_repository(), get_knowledge_manager(), get_learning_manager(), get_memory_manager(), get_orchestrator() (+7 more)

### Community 89 - "ProjectRepository"
Cohesion: 0.17
Nodes (6): get_project_service(), ProjectContextProvider, Any, ProjectRepository, ABC, UUID

### Community 90 - "ASTNode"
Cohesion: 0.26
Nodes (8): ASTNode, DocumentElement, parse_docx_content(), parse_pdf_content(), parse_pptx_content(), parse_xlsx_content(), Any, ExtractedContent

### Community 91 - "PdfRenderer"
Cohesion: 0.17
Nodes (11): Exception, Raised when the requested output format is not supported., Raised when document rendering fails., Base document renderer error., Raised when a render request fails validation., RendererError, RenderExecutionError, RenderValidationError (+3 more)

### Community 92 - "MemoryStore"
Cohesion: 0.16
Nodes (9): MemoryStore, ABC, UUID, Persist a memory item., Retrieve a memory item by id., Search memory items matching the query., Delete a memory item. Returns True if removed., Update an existing memory item. (+1 more)

### Community 93 - "PlanStep"
Cohesion: 0.19
Nodes (11): _find_plan_step(), UUID, _order_steps(), Exception, UUID, Raised when task execution fails irrecoverably., TaskExecutorError, PlanStep (+3 more)

### Community 94 - "models.py"
Cohesion: 0.20
Nodes (10): APIKeyCreateResult, APIKeyStatus, Permission, BaseModel, Enum, str, Returned once on creation — includes raw api_key; never persisted., Role (+2 more)

### Community 95 - "get_session_factory"
Cohesion: 0.18
Nodes (8): async_sessionmaker, get_polling_service(), Any, Long-polling transport for Telegram (production, no webhook/domain required)., TelegramPollingService, get_db_session(), get_session_factory(), AsyncSession

### Community 96 - "ClientIntelligenceSources"
Cohesion: 0.28
Nodes (9): _dedupe(), _iter_texts(), PreferenceAnalyzer, Finds style/format/constraint preferences — soft heuristics only., ClientIntelligenceResult, ClientIntelligenceSources, IntelligenceSignal, BaseModel (+1 more)

### Community 97 - "KnowledgeMigrationService"
Cohesion: 0.22
Nodes (8): KnowledgeMigrationService, _parse_uuid(), Any, UUID, Migrates client document archives into Client Knowledge Base., KnowledgeMigrationSkill, Any, Migrates client document archives into Knowledge Base.

### Community 98 - "BackgroundTaskRecord"
Cohesion: 0.24
Nodes (7): BackgroundTaskRecord, Persisted internal background task — no external broker., PostgresTaskQueueRepository, AsyncSession, UUID, PostgreSQL-backed internal queue (no external broker)., _to_task()

### Community 99 - "AI Employee OS"
Cohesion: 0.13
Nodes (15): AI Employee OS, Backup / restore, CI, Environment variables, Monitoring, Production setup, Security notes, Архитектура (кратко) (+7 more)

### Community 100 - "Diagnosing Bugs"
Cohesion: 0.14
Nodes (13): Completion criterion — a tight loop that goes red, Diagnosing Bugs, Minimise, Non-deterministic bugs, Phase 1 — Build a feedback loop, Phase 2 — Reproduce + minimise, Phase 3 — Hypothesise, Phase 4 — Instrument (+5 more)

### Community 101 - "Find Skills"
Cohesion: 0.14
Nodes (13): Common Skill Categories, Find Skills, How to Help Users Find Skills, Step 1: Understand What They Need, Step 2: Check the Leaderboard First, Step 3: Search for Skills, Step 4: Verify Quality Before Recommending, Step 5: Present Options to the User (+5 more)

### Community 102 - "AnalyticsResult"
Cohesion: 0.22
Nodes (8): _merge_insights(), _as_uuid(), prepare_analytics_memory_items(), UUID, AnalyticsResult, AnalyticsValidator, test_models_validation(), test_quality_checks()

### Community 103 - "CompositeAnalyticsDataProvider"
Cohesion: 0.21
Nodes (9): AnalyticsManager, Runs read-only analytics over existing sources — does not store its own data., AnalyticsNode, LangGraph-ready node — analytics report AST for Document/Presentation chains., CompositeAnalyticsDataProvider, Aggregates read-only fragments from optional repositories/context., AnalyticsQueryBuilder, Builds a read-only analytics dataset from request + providers. (+1 more)

### Community 104 - "compute_all_metrics"
Cohesion: 0.18
Nodes (10): compute_client_metrics(), Any, compute_execution_metrics(), compute_quality_metrics(), Any, compute_all_metrics(), Any, compute_project_metrics() (+2 more)

### Community 105 - "get_client_intelligence_manager"
Cohesion: 0.19
Nodes (8): get_client_intelligence_manager(), ClientIntelligenceBuilder, _merge_signals(), Builds ClientProfile from existing system fragments — no persistence., _default_recommendations(), ProfileBuilder, Assembles ClientProfile from analyzer signals and source fragments., _unique()

### Community 106 - "PptxRenderer"
Cohesion: 0.21
Nodes (5): PptxStyleExtractor, Any, PptxRenderer, Any, Presentation

### Community 107 - "ClientIntelligenceAnalyzer"
Cohesion: 0.18
Nodes (9): ClientIntelligenceAnalyzer, Runs specialized analyzers and optional LLM enrichment., CommunicationAnalyzer, Infers tone/language/format — soft heuristics only., HistoryAnalyzer, Looks at past projects/artifacts/patterns — soft heuristics only., Finds constraints and approval requirements — soft heuristics only., RiskAnalyzer (+1 more)

### Community 108 - "parse_creation_response"
Cohesion: 0.30
Nodes (12): _parse_ast_node(), parse_creation_response(), Any, creation_ast_json(), settings(), test_ast_validator(), test_creation_to_renderer_preparation(), test_document_ast_generation() (+4 more)

### Community 109 - ".process_bytes"
Cohesion: 0.15
Nodes (7): UUID, FileDetector, DetectedFile, FileCategory, BaseModel, str, detector()

### Community 110 - "PostgresKnowledgeStore"
Cohesion: 0.26
Nodes (7): PostgresKnowledgeStore, AsyncSession, UUID, PostgreSQL-backed knowledge store. Semantic search via Qdrant is deferred., _to_item(), KnowledgeRecord, Persisted client knowledge item — PostgreSQL foundation for Knowledge Base.

### Community 111 - "models.py"
Cohesion: 0.19
Nodes (11): _build_state_update(), Any, ApprovalStatus, PlanStatus, str, QualityCheckResult, StepStatus, TaskExecutionStatus (+3 more)

### Community 112 - ".review"
Cohesion: 0.15
Nodes (9): ABC, Any, Review execution output against user goal and context., ReviewerInterface, build_reviewer_user_message(), Any, Exception, Raised when reviewer analysis fails. (+1 more)

### Community 113 - "ResearchType"
Cohesion: 0.15
Nodes (8): Enum, str, ResearchType, Any, LangGraph-ready node — research then hand off to strategy/document skills., ResearchNode, build_research_user_message(), Any

### Community 114 - "ResearchRequest"
Cohesion: 0.33
Nodes (11): BaseModel, ResearchFinding, ResearchInsight, ResearchRequest, _default_summary(), _fallback(), _merge_insights(), parse_research_interpretation() (+3 more)

### Community 115 - "Skill"
Cohesion: 0.16
Nodes (7): ABC, Any, Return skill metadata., Return capabilities provided by this skill., Execute a task delegated to this skill., Base interface for system skills., Skill

### Community 116 - "WorkspaceRepository"
Cohesion: 0.21
Nodes (4): ABC, UUID, Persistence contract for Workspace, Session, and Conversation., WorkspaceRepository

### Community 117 - "Roadmap — AI Employee OS"
Cohesion: 0.14
Nodes (14): Roadmap — AI Employee OS, Метрики успеха по этапам, Принципы приоритизации, Этап 0 — Foundation ✅, Этап 10 — Learning & Production Hardening, Этап 1 — Infrastructure & Backend Skeleton, Этап 2 — LangGraph Core & Executive Agent, Этап 3 — Memory Layer (+6 more)

### Community 118 - "Test-Driven Development"
Cohesion: 0.15
Nodes (10): Designing for Mockability, When to Mock, Anti-patterns, Rules of the loop, Seams — where tests go, Test-Driven Development, What a good test is, Bad Tests (+2 more)

### Community 119 - "ClientRepository"
Cohesion: 0.23
Nodes (5): get_client_service(), ClientRepository, ABC, UUID, Case-insensitive lookup of a BUSINESS client by exact name.          Default imp

### Community 120 - "is_telegram_user_client"
Cohesion: 0.29
Nodes (10): analyze_client_intelligence(), ClientIntelligenceAnalyzeRequest, ClientIntelligenceResponse, get_client_intelligence(), BaseModel, UUID, client_metadata_value(), is_business_client() (+2 more)

### Community 121 - "TimelineRecorder"
Cohesion: 0.19
Nodes (5): Any, Starts and finishes execution traces — observation only., Records per-node timeline events without changing workflow logic., TimelineRecorder, Tracer

### Community 122 - "test_api_v1.py"
Cohesion: 0.24
Nodes (11): api_client(), artifact_service(), FakeAgentRuntime, Any, AsyncClient, test_artifacts_create_and_get(), test_background_tasks(), test_execution_run() (+3 more)

### Community 123 - "ArtifactStatus"
Cohesion: 0.29
Nodes (9): ArtifactStatus, str, ArtifactNewVersionRequest, ArtifactUploadRequest, ArtifactVersionCreate, BaseModel, test_create_new_version(), test_get_latest_version() (+1 more)

### Community 124 - "ObservabilityLogger"
Cohesion: 0.29
Nodes (4): ObservabilityLogger, Any, Centralized observation logger — uses existing trace_id, does not replace loggin, test_logger_uses_trace_id()

### Community 125 - "models.py"
Cohesion: 0.21
Nodes (9): UUID, sync_node_from_plan_step(), _topological_order(), ExecutionControlStatus, NodeStatus, BaseModel, str, TelegramProgressLine (+1 more)

### Community 126 - "BackgroundTask"
Cohesion: 0.23
Nodes (7): BackgroundTask, BackgroundTaskStatus, BaseModel, Enum, str, Internal background task — no external broker., Pull one queued task and assign it to a worker.

### Community 127 - "read_file_bytes"
Cohesion: 0.32
Nodes (9): read_file_bytes(), test_file_detector_magic_bytes(), Path, test_docx_extraction(), test_image_extraction(), test_pdf_extraction(), test_pptx_extraction(), test_txt_extraction() (+1 more)

### Community 128 - "test_client_intelligence.py"
Cohesion: 0.21
Nodes (8): FakeClientService, settings(), test_api_intelligence(), test_builder_and_manager(), test_context_integration(), test_profile_models(), test_skill_registry_and_execute(), test_workspace_integration()

### Community 129 - "ClientProfile"
Cohesion: 0.27
Nodes (6): prepare_client_intelligence_memory_items(), Prepare memory candidates — never auto-remembers., ClientProfile, ProfileValidator, Quality checks for client intelligence profiles., test_quality_checks()

### Community 130 - ".extract"
Cohesion: 0.20
Nodes (7): KnowledgeExtractorError, Any, Exception, Raised when knowledge extraction fails., filter_items(), should_persist_item(), build_knowledge_extraction_message()

### Community 131 - "MetricsCollector"
Cohesion: 0.18
Nodes (3): MetricsCollector, In-memory metrics facade — observation only., MetricsSnapshot

### Community 132 - "BackgroundTaskNode"
Cohesion: 0.24
Nodes (8): BackgroundTaskNode, _log_node(), Any, UUID, LangGraph-ready node for enqueueing background work — not wired into main workfl, _to_uuid(), test_background_task_node_skips_without_type(), test_background_task_node_with_workspace()

### Community 133 - "ingest_archive"
Cohesion: 0.35
Nodes (10): _artifact_type(), _ensure_agency_client(), ingest_archive(), main(), _mime_for(), parse_args(), AsyncSession, Namespace (+2 more)

### Community 134 - "Project Context — AI Employee OS"
Cohesion: 0.18
Nodes (11): Project Context — AI Employee OS, Vision, Архитектурные основы, Главный принцип, Запрещено, Ключевые возможности, Ограничения и границы, Правильно (+3 more)

### Community 135 - "Ask Matt"
Cohesion: 0.20
Nodes (9): Ask Matt, Codebase health, Context hygiene, Crossing sessions, On-ramps, Precondition, Standalone, The main flow: idea → ship (+1 more)

### Community 136 - "TelegramFlowMode"
Cohesion: 0.24
Nodes (8): build_pending_clarification(), merge_clarification_answer(), Combine the original task goal with the user's clarification answer., PendingClarification, BaseModel, Enum, str, TelegramFlowMode

### Community 137 - "AnalyticsDataProvider"
Cohesion: 0.29
Nodes (6): AnalyticsAnalyzerInterface, AnalyticsDataProvider, AnalyticsManagerInterface, ABC, Any, Read-only adapter over existing system sources.

### Community 138 - "executions.py"
Cohesion: 0.31
Nodes (8): cancel_execution(), get_execution(), get_execution_progress(), pause_execution(), ExecutionControlResponse, ExecutionDetailResponse, ExecutionProgressResponse, BaseModel

### Community 139 - "security.py"
Cohesion: 0.42
Nodes (9): create_api_key(), CreateAPIKeyRequest, list_api_keys(), list_audit_events(), _principal(), BaseModel, Request, UUID (+1 more)

### Community 140 - "extract_business_subject"
Cohesion: 0.36
Nodes (8): _clean_candidate(), extract_business_subject(), _extract_heuristic(), _extract_with_llm(), ExtractedSubject, _parse_json_object(), Extract the business client a chat task is *for* (e.g. "КП для Яндекса" → "Яндек, test_extractor_heuristic_fallback_no_gateway()

### Community 141 - "builder.py"
Cohesion: 0.42
Nodes (7): _fetch_provider_safe(), _log_node(), _merge_fragments(), _parse_uuid(), _provider_contributed(), Any, UUID

### Community 142 - "KnowledgeMigrationNode"
Cohesion: 0.29
Nodes (7): _is_telegram_migration_skip(), KnowledgeMigrationNode, _log_node(), Any, UUID, LangGraph-ready node for knowledge migration — not wired into main workflow yet., _to_uuid()

### Community 143 - "SQLAlchemyProjectRepository"
Cohesion: 0.33
Nodes (3): AsyncSession, UUID, SQLAlchemyProjectRepository

### Community 144 - ".__init__"
Cohesion: 0.20
Nodes (5): AccessPolicy, Infrastructure access checks — no business decisions., APIKeyProvider, Hash/generate helpers for API keys — never stores raw tokens., test_api_key_provider_hash_stable()

### Community 145 - "release_on_server.py"
Cohesion: 0.44
Nodes (7): main(), _req(), audit(), connect(), main(), run(), SSHClient

### Community 146 - "TaskQueueRepository"
Cohesion: 0.24
Nodes (5): ABC, UUID, Atomically pick the highest-priority QUEUED task and mark RUNNING., Persistence contract for the internal task queue., TaskQueueRepository

### Community 147 - "test_workspace.py"
Cohesion: 0.20
Nodes (7): manager(), service(), test_conversation_not_memory(), test_session_lifecycle(), test_workspace_context_provider(), test_workspace_manager_active_pointers(), test_workspace_model_and_open()

### Community 148 - "Architecture — AI Employee OS"
Cohesion: 0.20
Nodes (10): Admin Panel, Architecture — AI Employee OS, Brand Style Engine, Client Knowledge Pipeline & Knowledge Migration, LangGraph Runtime, Memory Architecture, Overview, Request Pipeline (+2 more)

### Community 149 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 150 - "SKILL.md"
Cohesion: 0.22
Nodes (8): Further Notes, Implementation Decisions, Out of Scope, Problem Statement, Process, Solution, Testing Decisions, User Stories

### Community 151 - ".collect"
Cohesion: 0.42
Nodes (6): _artifact_dict(), _as_uuid(), _project_dict(), Any, UUID, _task_dict()

### Community 152 - "ArtifactVersionRepository"
Cohesion: 0.33
Nodes (4): get_artifact_service(), ArtifactVersionRepository, ABC, UUID

### Community 153 - "workspace.py"
Cohesion: 0.39
Nodes (7): get_workspace(), get_workspace_by_client(), open_workspace(), UUID, BaseModel, WorkspaceOpenRequest, WorkspaceSnapshot

### Community 154 - "build_brand_profile"
Cohesion: 0.53
Nodes (8): build_brand_profile(), _build_colors(), _build_document_rules(), _build_layout_rules(), _build_typography(), _build_visual_elements(), Any, UUID

### Community 155 - "ClientIntelligenceManager"
Cohesion: 0.47
Nodes (6): _as_uuid(), ClientIntelligenceManager, Any, UUID, Aggregates existing Memory/Knowledge/Learning/Workspace data into ClientProfile., _skipped_telegram_intelligence_result()

### Community 156 - "SQLAlchemyClientRepository"
Cohesion: 0.42
Nodes (3): AsyncSession, UUID, SQLAlchemyClientRepository

### Community 157 - "SecurityMiddleware"
Cohesion: 0.22
Nodes (6): Any, Request, Response, Checks API key, attaches actor, writes audit — no business logic., SecurityMiddleware, BaseHTTPMiddleware

### Community 158 - "Process"
Cohesion: 0.25
Nodes (7): 1. Pin the fixed point, 2. Identify the spec source, 3. Identify the standards sources, 4. Spawn both sub-agents in parallel, 5. Aggregate, Process, Why two axes

### Community 159 - ".enrich_with_llm"
Cohesion: 0.32
Nodes (5): _evidence_lines(), parse_llm_intelligence(), Any, build_analyzer_user_message(), test_llm_analyzer_parse()

### Community 160 - "intelligence.py"
Cohesion: 0.36
Nodes (5): ClientIntelligenceBuilderInterface, ClientIntelligenceManagerInterface, ABC, Any, UUID

### Community 161 - ".__call__"
Cohesion: 0.32
Nodes (5): LearningNode, Any, UUID, LangGraph-ready learning node — optional; not required in main workflow., _to_uuid()

### Community 162 - "SQLAlchemyArtifactVersionRepository"
Cohesion: 0.36
Nodes (3): AsyncSession, UUID, SQLAlchemyArtifactVersionRepository

### Community 164 - "WorkspaceContextProvider"
Cohesion: 0.32
Nodes (5): _parse_uuid(), Any, UUID, Injects workspace state into ExecutionContext as workspace_context., WorkspaceContextProvider

### Community 165 - "Architecture Decision Records (ADR)"
Cohesion: 0.25
Nodes (8): Architecture Decision Records (ADR), Когда создавать ADR, Нумерация, Планируемые ADR, Связанные документы, Формат, Что такое ADR, Шаблон

### Community 166 - ".interpret"
Cohesion: 0.43
Nodes (4): _fallback_interpretation(), parse_analytics_interpretation(), Any, build_analytics_user_message()

### Community 167 - "create_artifact"
Cohesion: 0.52
Nodes (6): create_artifact(), create_artifact_version(), get_artifact(), get_artifact_versions(), UploadFile, UUID

### Community 168 - "run_execution"
Cohesion: 0.38
Nodes (5): Request, run_execution(), ExecutionRunRequest, ExecutionRunResponse, BaseModel

### Community 169 - "learning.py"
Cohesion: 0.43
Nodes (6): LearningFeedbackRequest, list_learning_rules(), list_learning_rules_for_client(), BaseModel, UUID, submit_learning_feedback()

### Community 170 - "parse_revision_response"
Cohesion: 0.33
Nodes (5): ASTNodeType, str, _parse_ast_node(), parse_revision_response(), Any

### Community 171 - "prepare_knowledge_memory_items"
Cohesion: 0.33
Nodes (5): prepare_knowledge_memory_items(), UUID, Prepare memory candidates from knowledge migration without auto-saving., KnowledgeMigrationResult, BaseModel

### Community 172 - "ResearchManagerInterface"
Cohesion: 0.38
Nodes (3): ABC, ResearcherInterface, ResearchManagerInterface

### Community 173 - "ResearchQueryBuilder"
Cohesion: 0.33
Nodes (4): Builds search queries from goal + context — no keyword routing., ResearchQueryBuilder, _type_hint(), test_query_builder()

### Community 174 - "SecretsManager"
Cohesion: 0.33
Nodes (4): Any, Reads configured secrets and redacts them from log-like strings., SecretsManager, test_secrets_redaction()

### Community 175 - "InMemoryTaskQueueRepository"
Cohesion: 0.29
Nodes (4): InMemoryTaskQueueRepository, In-process queue store — foundation without external brokers., queue_manager(), queue()

### Community 176 - "Core Components"
Cohesion: 0.29
Nodes (7): 1. Executive Agent, 2. Capability Planner, 3. Planner, 4. Task Executor, 5. Skill Registry, 6. Reviewer Agent (Quality Gate), Core Components

### Community 177 - "Document Intelligence"
Cohesion: 0.29
Nodes (7): Artifact System, Document AST, Document Intelligence, Document Reverse Engineering, Template Engine, Внутренние абстракции, Возможности

### Community 178 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 179 - "env.py"
Cohesion: 0.47
Nodes (4): do_run_migrations(), run_async_migrations(), run_migrations_online(), Connection

### Community 180 - "TelegramAdapterInterface"
Cohesion: 0.40
Nodes (4): ABC, Any, Transport adapter: Telegram Update → AgentRuntime → reply., TelegramAdapterInterface

### Community 181 - "models.py"
Cohesion: 0.53
Nodes (5): BaseModel, TelegramCallbackQuery, TelegramChat, TelegramMessage, TelegramUser

### Community 185 - "run_research"
Cohesion: 0.47
Nodes (5): get_research(), BaseModel, UUID, ResearchRunRequest, run_research()

### Community 186 - "ClientIntelligenceNode"
Cohesion: 0.33
Nodes (3): ClientIntelligenceNode, Any, LangGraph-ready node — builds ClientProfile without auto-persisting.

### Community 187 - ".analyze"
Cohesion: 0.47
Nodes (4): DocumentAnalyzerInterface, ABC, UUID, Build document representation and AST from extracted content.

### Community 188 - "prepare_document_memory_items"
Cohesion: 0.40
Nodes (4): prepare_document_memory_items(), UUID, Prepare memory candidates from a document representation without auto-saving., Any

### Community 190 - ".extract"
Cohesion: 0.40
Nodes (4): KnowledgeExtractorInterface, ABC, Any, Extract universal knowledge items from a document.

### Community 191 - "KnowledgeContextProvider"
Cohesion: 0.33
Nodes (3): KnowledgeContextProvider, Any, Injects Client Knowledge Base into ExecutionContext as knowledge_context.

### Community 192 - ".execute"
Cohesion: 0.47
Nodes (4): ABC, UUID, Execute plan steps via registered skills., TaskExecutorInterface

### Community 195 - "Cross-Cutting Concerns"
Cohesion: 0.33
Nodes (6): Artifact Versioning, Context Builder, Cross-Cutting Concerns, Human Approval Layer, LLM Gateway, Observability

### Community 196 - "orchestration_parser.py"
Cohesion: 0.60
Nodes (4): parse_execution_graph(), parse_execution_state(), parse_task_execution(), Any

### Community 198 - "competitor_analysis.py"
Cohesion: 0.60
Nodes (4): empty_competitor_analysis(), normalize_competitor_analysis(), Any, Competitor analysis framework structure helpers — no decisions.

### Community 199 - "marketing_plan.py"
Cohesion: 0.50
Nodes (4): empty_marketing_plan(), normalize_marketing_plan(), Any, Marketing plan framework structure helpers — no decisions.

### Community 200 - "positioning.py"
Cohesion: 0.50
Nodes (4): empty_positioning(), normalize_positioning(), Any, Positioning framework structure helpers — no decisions.

### Community 201 - "backup_postgres.py"
Cohesion: 0.60
Nodes (4): main(), parse_args(), Namespace, to_libpq_url()

### Community 202 - "restore_postgres.py"
Cohesion: 0.60
Nodes (4): main(), parse_args(), Namespace, to_libpq_url()

### Community 203 - "Пользовательские сценарии"
Cohesion: 0.40
Nodes (5): Onboarding клиента (Knowledge Migration), Пользовательские сценарии, Простой запрос, Работа с документами, Сложный запрос

### Community 204 - "hitl-loop.template.sh"
Cohesion: 0.83
Nodes (3): capture(), hitl-loop.template.sh script, step()

### Community 205 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 206 - "graphify reference: commit hook and native AGENTS.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native AGENTS.md integration, graphify reference: commit hook and native AGENTS.md integration

### Community 207 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 208 - "Local setup"
Cohesion: 0.50
Nodes (4): Development services, Local setup, Local tests, Migrations (local)

## Knowledge Gaps
- **203 isolated node(s):** `entrypoint.sh script`, `provision_production.sh script`, `AGENCY_ARCHIVE_PATH`, `Context hygiene`, `On-ramps` (+198 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Settings` to `test_client_intelligence.py`, `LLMGateway`, `CapabilityRegistry`, `StrategyRequest`, `PresentationPlanner`, `QualityGate`, `create_context_builder`, `RevisionAgent`, `mock_gateway`, `Orchestrator`, `MemoryManager`, `QdrantSemanticMemory`, `build_executive_graph`, `ResearchManager`, `build_e2e_registry`, `MemoryItem`, `create_capability_registry`, `Client`, `SecretsManager`, `KnowledgeManager`, `llm_fixtures.py`, `build_readiness_payload`, `E2EContextBuilderNode`, `AnalyticsAnalyzer`, `build_execution_graph`, `MemoryStore`, `get_session_factory`, `parse_creation_response`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Why does `build_telegram_bot()` connect `Settings` to `TelegramAdapter`, `create_context_builder`, `BusinessClientResolver`, `AgentRuntime`, `SQLAlchemyProjectRepository`, `mock_gateway`, `LearningRule`, `Orchestrator`, `QdrantSemanticMemory`, `ClientIntelligenceManager`, `SQLAlchemyClientRepository`, `WorkspaceManager`, `Conversation`, `build_executive_graph`, `ResearchManager`, `SQLAlchemyArtifactVersionRepository`, `ArtifactRepository`, `InMemoryLongTermMemory`, `MemoryItem`, `create_capability_registry`, `WorkspaceService`, `ArtifactService`, `KnowledgeManager`, `ExecutionStore`, `get_session_factory`, `get_client_intelligence_manager`, `ClientIntelligenceAnalyzer`, `PostgresKnowledgeStore`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `LLMGateway` connect `LLMGateway` to `StrategyRequest`, `CapabilityRegistry`, `.extract`, `PresentationPlanner`, `QualityGate`, `ResponseParseError`, `create_context_builder`, `AgentRuntime`, `RevisionAgent`, `Settings`, `mock_gateway`, `PresentationDesigner`, `build_executive_graph`, `ResearchManager`, `build_e2e_registry`, `create_capability_registry`, `ResearchQueryBuilder`, `Client`, `KnowledgeManager`, `AnalyticsDataset`, `E2EContextBuilderNode`, `AnalyticsAnalyzer`, `deps.py`, `CompositeAnalyticsDataProvider`, `get_client_intelligence_manager`, `ClientIntelligenceAnalyzer`, `.review`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `CapabilityRegistry` (e.g. with `TelegramAdapter` and `TelegramBot`) actually correct?**
  _`CapabilityRegistry` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 50 inferred relationships involving `LLMGateway` (e.g. with `AgentRuntime` and `ExecutiveAgent`) actually correct?**
  _`LLMGateway` has 50 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `Settings` (e.g. with `LLMGateway` and `OpenRouterProvider`) actually correct?**
  _`Settings` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `TelegramProductFlow` (e.g. with `TelegramAdapter` and `TelegramBot`) actually correct?**
  _`TelegramProductFlow` has 34 INFERRED edges - model-reasoned connections that need verification._