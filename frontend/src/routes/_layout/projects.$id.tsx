import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Cpu,
  Download,
  FileText,
  Maximize2,
  Wand2,
} from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { ProjectsService } from "@/client"
import type {
  ComponentItemPublic,
  DiagramEdgePublic,
  DiagramNodePublic,
  DiagramVersionPublic,
  GenerationRequest,
} from "@/client/types.gen"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"

export const Route = createFileRoute("/_layout/projects/$id")({
  component: ArchitectureWorkspace,
  head: () => ({
    meta: [{ title: "Architecture Workspace" }],
  }),
})

// ─── Node styling ─────────────────────────────────────────────────────────────

function nodeStyleByType(type: string): React.CSSProperties {
  const styles: Record<string, React.CSSProperties> = {
    networking: { background: "#dbeafe", border: "1px solid #3b82f6" },
    compute: { background: "#dcfce7", border: "1px solid #22c55e" },
    database: { background: "#f3e8ff", border: "1px solid #a855f7" },
    serverless: { background: "#fef9c3", border: "1px solid #eab308" },
    messaging: { background: "#ffedd5", border: "1px solid #f97316" },
    storage: { background: "#e0f2fe", border: "1px solid #0ea5e9" },
    monitoring: { background: "#fce7f3", border: "1px solid #ec4899" },
    security: { background: "#fee2e2", border: "1px solid #ef4444" },
    identity: { background: "#f0fdf4", border: "1px solid #86efac" },
    cache: { background: "#fdf4ff", border: "1px solid #d946ef" },
  }
  return styles[type] ?? { background: "#f1f5f9", border: "1px solid #94a3b8" }
}

function toReactFlowNode(n: DiagramNodePublic): Node {
  return {
    id: n.id,
    position: { x: n.x_position ?? 0, y: n.y_position ?? 0 },
    data: { label: n.label, type: n.node_type, provider: n.provider },
    type: "default",
    style: nodeStyleByType(n.node_type),
  }
}

function toReactFlowEdge(e: DiagramEdgePublic): Edge {
  return {
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    label: e.label ?? undefined,
    type: "smoothstep",
  }
}

// ─── Component badge color ─────────────────────────────────────────────────────

function componentBadgeVariant(type: string) {
  const map: Record<string, string> = {
    networking: "bg-blue-100 text-blue-800",
    compute: "bg-green-100 text-green-800",
    database: "bg-purple-100 text-purple-800",
    serverless: "bg-yellow-100 text-yellow-800",
    storage: "bg-sky-100 text-sky-800",
    monitoring: "bg-pink-100 text-pink-800",
    security: "bg-red-100 text-red-800",
  }
  return map[type] ?? "bg-slate-100 text-slate-800"
}

// ─── Collapsible section ───────────────────────────────────────────────────────

function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
}: {
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border rounded-md overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium bg-muted/50 hover:bg-muted transition-colors"
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        {title}
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  )
}

// ─── Left Panel ────────────────────────────────────────────────────────────────

function LeftPanel({
  projectTitle,
  projectId,
  onGenerate,
  onRefine,
  isPending,
  versions,
  promptHistory,
}: {
  projectTitle: string
  projectId: string
  onGenerate: (prompt: string) => void
  onRefine: (prompt: string) => void
  isPending: boolean
  versions: DiagramVersionPublic[]
  promptHistory: string[]
}) {
  const queryClient = useQueryClient()
  const [collapsed, setCollapsed] = useState(false)
  const [prompt, setPrompt] = useState("")
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState(projectTitle)

  const updateTitleMutation = useMutation({
    mutationFn: (title: string) =>
      ProjectsService.updateProject({ projectId, requestBody: { title } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] })
      toast.success("Title updated")
    },
    onError: () => toast.error("Failed to update title"),
  })

  useEffect(() => {
    setTitleValue(projectTitle)
  }, [projectTitle])

  function handleTitleBlur() {
    setEditingTitle(false)
    if (titleValue.trim() && titleValue !== projectTitle) {
      updateTitleMutation.mutate(titleValue.trim())
    }
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-4 w-10 border-r bg-background">
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)} title="Expand">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col w-72 border-r bg-background shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="text-sm font-semibold truncate">Project</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setCollapsed(true)} title="Collapse">
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {/* Title */}
          <div>
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Title</label>
            {editingTitle ? (
              <input
                className="mt-1 w-full text-sm font-semibold border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
                value={titleValue}
                onChange={(e) => setTitleValue(e.target.value)}
                onBlur={handleTitleBlur}
                onKeyDown={(e) => e.key === "Enter" && handleTitleBlur()}
                autoFocus
              />
            ) : (
              <p
                className="mt-1 text-sm font-semibold cursor-pointer hover:text-primary truncate"
                onClick={() => setEditingTitle(true)}
                title="Click to edit"
              >
                {titleValue || "Untitled"}
              </p>
            )}
          </div>

          <Separator />

          {/* Prompt */}
          <div className="space-y-2">
            <label className="text-xs text-muted-foreground uppercase tracking-wide">Prompt</label>
            <Textarea
              placeholder="Describe your architecture…"
              className="min-h-[120px] text-sm resize-none"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="flex gap-2">
              <Button
                className="flex-1"
                size="sm"
                onClick={() => prompt.trim() && onGenerate(prompt)}
                disabled={isPending || !prompt.trim()}
              >
                <Wand2 className="mr-1 h-3.5 w-3.5" />
                Generate
              </Button>
              <Button
                className="flex-1"
                size="sm"
                variant="secondary"
                onClick={() => prompt.trim() && onRefine(prompt)}
                disabled={isPending || !prompt.trim()}
              >
                Refine
              </Button>
            </div>
          </div>

          {/* Prompt history */}
          {promptHistory.length > 0 && (
            <CollapsibleSection title="Prompt History">
              <div className="space-y-2">
                {promptHistory.map((p, i) => (
                  <button
                    key={i}
                    className="w-full text-left text-xs text-muted-foreground hover:text-foreground p-2 rounded border hover:bg-muted transition-colors"
                    onClick={() => setPrompt(p)}
                    type="button"
                  >
                    <span className="line-clamp-2">{p}</span>
                  </button>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Version history */}
          {versions.length > 0 && (
            <CollapsibleSection title="Version History">
              <div className="space-y-1">
                {versions.map((v) => (
                  <div key={v.id} className="flex items-center justify-between text-xs p-2 rounded border">
                    <span className="font-medium">v{v.version_number}</span>
                    <span className="text-muted-foreground">
                      {v.created_at ? new Date(v.created_at).toLocaleDateString() : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

// ─── Center Panel ──────────────────────────────────────────────────────────────

function CenterPanel({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  flowRef,
}: {
  nodes: Node[]
  edges: Edge[]
  onNodesChange: ReturnType<typeof useNodesState>[2]
  onEdgesChange: ReturnType<typeof useEdgesState>[2]
  flowRef: React.MutableRefObject<{ fitView: () => void } | null>
}) {
  const rfRef = useRef<{ fitView: () => void } | null>(null)

  const onInit = useCallback(
    (instance: { fitView: () => void }) => {
      rfRef.current = instance
      flowRef.current = instance
    },
    [flowRef],
  )

  return (
    <div className="flex-1 flex flex-col min-w-0">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b bg-background shrink-0">
        <Button
          variant="outline"
          size="sm"
          onClick={() => rfRef.current?.fitView()}
          title="Fit view"
        >
          <Maximize2 className="h-3.5 w-3.5 mr-1" />
          Fit View
        </Button>
        <span className="text-xs text-muted-foreground ml-auto">
          {nodes.length} nodes · {edges.length} edges
        </span>
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground pointer-events-none z-10">
            <Cpu className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm">Enter a prompt and click Generate to create your architecture diagram</p>
          </div>
        )}
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onInit={onInit}
          fitView
          attributionPosition="bottom-left"
        >
          <Background />
          <Controls />
          <MiniMap zoomable pannable />
        </ReactFlow>
      </div>
    </div>
  )
}

// ─── Right Panel ───────────────────────────────────────────────────────────────

function RightPanel({
  components,
  notes,
  projectId,
}: {
  components: ComponentItemPublic[]
  notes: string
  projectId: string
}) {
  const [collapsed, setCollapsed] = useState(false)

  async function exportMarkdown() {
    try {
      const res = await ProjectsService.exportMarkdown({ projectId })
      const blob = new Blob([JSON.stringify(res)], { type: "text/markdown" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = "architecture.md"
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error("Export failed")
    }
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-4 w-10 border-l bg-background">
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(false)} title="Expand">
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col w-72 border-l bg-background shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="text-sm font-semibold">Details</span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setCollapsed(true)} title="Collapse">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <Tabs defaultValue="components" className="flex flex-col flex-1 min-h-0">
        <TabsList className="mx-4 mt-3 shrink-0">
          <TabsTrigger value="components" className="flex-1">Components</TabsTrigger>
          <TabsTrigger value="notes" className="flex-1">Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="components" className="flex-1 min-h-0 mt-0">
          <ScrollArea className="h-full">
            <div className="p-4 space-y-2">
              {components.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-8">
                  No components yet. Generate a diagram to see components.
                </p>
              )}
              {components.map((c) => (
                <div key={c.id} className="border rounded-md p-3 space-y-1">
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-sm font-medium truncate">{c.name}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${componentBadgeVariant(c.component_type)}`}
                    >
                      {c.component_type}
                    </span>
                  </div>
                  {c.provider && (
                    <p className="text-xs text-muted-foreground">{c.provider}</p>
                  )}
                  {c.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2">{c.description}</p>
                  )}
                  {c.role_summary && (
                    <p className="text-xs italic text-muted-foreground line-clamp-2">{c.role_summary}</p>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="notes" className="flex-1 min-h-0 mt-0">
          <ScrollArea className="h-full">
            <div className="p-4">
              {notes ? (
                <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed">{notes}</pre>
              ) : (
                <p className="text-xs text-muted-foreground text-center py-8">
                  No notes yet. Generate a diagram to see architecture notes.
                </p>
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>

      {/* Export buttons */}
      <div className="p-4 border-t space-y-2 shrink-0">
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Export</p>
        <div className="flex flex-col gap-1.5">
          <Button variant="outline" size="sm" className="justify-start" onClick={exportMarkdown}>
            <FileText className="mr-2 h-3.5 w-3.5" />
            Export Markdown
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="justify-start"
            onClick={() => toast.info("PNG export requires backend support")}
          >
            <Download className="mr-2 h-3.5 w-3.5" />
            Export PNG
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="justify-start"
            onClick={() => toast.info("SVG export requires backend support")}
          >
            <Download className="mr-2 h-3.5 w-3.5" />
            Export SVG
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Workspace ────────────────────────────────────────────────────────────

function ArchitectureWorkspace() {
  const { id } = Route.useParams()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [components, setComponents] = useState<ComponentItemPublic[]>([])
  const [notes, setNotes] = useState("")
  const [promptHistory, setPromptHistory] = useState<string[]>([])
  const flowRef = useRef<{ fitView: () => void } | null>(null)

  const { data: projectData } = useQuery({
    queryKey: ["project", id],
    queryFn: () => ProjectsService.readProject({ projectId: id }),
  })

  const { data: versionsData } = useQuery({
    queryKey: ["project-versions", id],
    queryFn: () => ProjectsService.listVersions({ projectId: id }),
  })

  const generateMutation = useMutation({
    mutationFn: (req: GenerationRequest) =>
      ProjectsService.generateDiagram({ projectId: id, requestBody: req }),
    onSuccess: (data) => {
      setNodes(data.nodes.map(toReactFlowNode))
      setEdges(data.edges.map(toReactFlowEdge))
      setComponents(data.components)
      setNotes(data.notes_markdown ?? data.diagram_version.notes_markdown ?? "")
      toast.success("Diagram generated")
      setTimeout(() => flowRef.current?.fitView(), 100)
    },
    onError: () => toast.error("Generation failed"),
  })

  const refineMutation = useMutation({
    mutationFn: (req: GenerationRequest) =>
      ProjectsService.refineDiagram({ projectId: id, requestBody: req }),
    onSuccess: (data) => {
      setNodes(data.nodes.map(toReactFlowNode))
      setEdges(data.edges.map(toReactFlowEdge))
      setComponents(data.components)
      setNotes(data.notes_markdown ?? data.diagram_version.notes_markdown ?? "")
      toast.success("Diagram refined")
      setTimeout(() => flowRef.current?.fitView(), 100)
    },
    onError: () => toast.error("Refinement failed"),
  })

  function handleGenerate(prompt: string) {
    setPromptHistory((h) => [prompt, ...h.filter((p) => p !== prompt)].slice(0, 10))
    generateMutation.mutate({
      prompt,
      cloud_context: projectData?.cloud_context ?? null,
      diagram_type: projectData?.diagram_type ?? null,
    })
  }

  function handleRefine(prompt: string) {
    setPromptHistory((h) => [prompt, ...h.filter((p) => p !== prompt)].slice(0, 10))
    refineMutation.mutate({
      prompt,
      cloud_context: projectData?.cloud_context ?? null,
      diagram_type: projectData?.diagram_type ?? null,
    })
  }

  const isPending = generateMutation.isPending || refineMutation.isPending

  return (
    <div className="flex h-full overflow-hidden -m-6">
      <LeftPanel
        projectTitle={projectData?.title ?? ""}
        projectId={id}
        onGenerate={handleGenerate}
        onRefine={handleRefine}
        isPending={isPending}
        versions={versionsData?.data ?? []}
        promptHistory={promptHistory}
      />

      <CenterPanel
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        flowRef={flowRef}
      />

      <RightPanel
        components={components}
        notes={notes}
        projectId={id}
      />
    </div>
  )
}
