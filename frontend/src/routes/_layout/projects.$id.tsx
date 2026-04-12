import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Download,
  FileText,
  Maximize2,
  Wand2,
  ZoomIn,
  ZoomOut,
} from "lucide-react"
import type {
  MouseEvent as ReactMouseEvent,
  ReactNode,
  WheelEvent as ReactWheelEvent,
} from "react"
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
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"

export const Route = createFileRoute("/_layout/projects/$id")({
  component: ArchitectureWorkspace,
  head: () => ({
    meta: [{ title: "Architecture Workspace" }],
  }),
})

// ─── Node styling ─────────────────────────────────────────────────────────────

type NodeStyle = {
  fill: string
  stroke: string
  textColor: string
}

type PromptRevisionSummary = {
  id: string
  prompt_text: string
}

type ProjectBundleResponse = {
  diagram_version: DiagramVersionPublic | null
  nodes?: DiagramNodePublic[]
  edges?: DiagramEdgePublic[]
  components?: ComponentItemPublic[]
  prompt_revisions?: PromptRevisionSummary[]
}

type MarkdownExportResponse = {
  content?: string
}

function nodeStyleByType(type: string): NodeStyle {
  const styles: Record<string, NodeStyle> = {
    networking: { fill: "#dbeafe", stroke: "#3b82f6", textColor: "#1e40af" },
    compute: { fill: "#dcfce7", stroke: "#22c55e", textColor: "#15803d" },
    database: { fill: "#f3e8ff", stroke: "#a855f7", textColor: "#7e22ce" },
    serverless: { fill: "#fef9c3", stroke: "#eab308", textColor: "#854d0e" },
    messaging: { fill: "#ffedd5", stroke: "#f97316", textColor: "#9a3412" },
    storage: { fill: "#e0f2fe", stroke: "#0ea5e9", textColor: "#0c4a6e" },
    monitoring: { fill: "#fce7f3", stroke: "#ec4899", textColor: "#9d174d" },
    security: { fill: "#fee2e2", stroke: "#ef4444", textColor: "#991b1b" },
    identity: { fill: "#f0fdf4", stroke: "#86efac", textColor: "#14532d" },
    cache: { fill: "#fdf4ff", stroke: "#d946ef", textColor: "#701a75" },
  }
  return (
    styles[type] ?? {
      fill: "#f1f5f9",
      stroke: "#94a3b8",
      textColor: "#334155",
    }
  )
}

// ─── Component badge color ─────────────────────────────────────────────────────

function componentBadgeClass(type: string) {
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
  children: ReactNode
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
        {open ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>
      {open && <div className="p-3">{children}</div>}
    </div>
  )
}

// ─── SVG Diagram Canvas ────────────────────────────────────────────────────────

const NODE_WIDTH = 140
const NODE_HEIGHT = 60

function DiagramCanvas({
  nodes,
  edges,
}: {
  nodes: DiagramNodePublic[]
  edges: DiagramEdgePublic[]
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [transform, setTransform] = useState({ x: 40, y: 40, scale: 1 })
  const [dragging, setDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0, tx: 0, ty: 0 })

  const nodeMap = new Map(nodes.map((n) => [n.id, n]))

  function handleWheel(e: ReactWheelEvent<SVGSVGElement>) {
    e.preventDefault()
    const factor = e.deltaY > 0 ? 0.9 : 1.1
    setTransform((t) => ({
      ...t,
      scale: Math.min(3, Math.max(0.2, t.scale * factor)),
    }))
  }

  function handleMouseDown(e: ReactMouseEvent<SVGSVGElement>) {
    if (e.button !== 0) return
    setDragging(true)
    setDragStart({
      x: e.clientX,
      y: e.clientY,
      tx: transform.x,
      ty: transform.y,
    })
  }

  function handleMouseMove(e: ReactMouseEvent<SVGSVGElement>) {
    if (!dragging) return
    setTransform((t) => ({
      ...t,
      x: dragStart.tx + (e.clientX - dragStart.x),
      y: dragStart.ty + (e.clientY - dragStart.y),
    }))
  }

  function handleMouseUp() {
    setDragging(false)
  }

  function fitView() {
    if (nodes.length === 0) return
    const xs = nodes.map((n) => n.x_position ?? 0)
    const ys = nodes.map((n) => n.y_position ?? 0)
    const minX = Math.min(...xs)
    const minY = Math.min(...ys)
    const maxX = Math.max(...xs) + NODE_WIDTH
    const maxY = Math.max(...ys) + NODE_HEIGHT
    const containerWidth = svgRef.current?.clientWidth ?? 800
    const containerHeight = svgRef.current?.clientHeight ?? 500
    const scaleX = (containerWidth - 80) / (maxX - minX)
    const scaleY = (containerHeight - 80) / (maxY - minY)
    const scale = Math.min(scaleX, scaleY, 2)
    setTransform({
      x: (containerWidth - (maxX - minX) * scale) / 2 - minX * scale,
      y: (containerHeight - (maxY - minY) * scale) / 2 - minY * scale,
      scale,
    })
  }

  // Compute edge path between two nodes
  function edgePath(src: DiagramNodePublic, tgt: DiagramNodePublic): string {
    const x1 = (src.x_position ?? 0) + NODE_WIDTH / 2
    const y1 = (src.y_position ?? 0) + NODE_HEIGHT / 2
    const x2 = (tgt.x_position ?? 0) + NODE_WIDTH / 2
    const y2 = (tgt.y_position ?? 0) + NODE_HEIGHT / 2
    const cx = (x1 + x2) / 2
    return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`
  }

  return (
    <div className="relative w-full h-full bg-dot-pattern overflow-hidden">
      {/* Toolbar */}
      <div className="absolute top-3 right-3 z-10 flex gap-1">
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() =>
            setTransform((t) => ({ ...t, scale: Math.min(3, t.scale * 1.2) }))
          }
        >
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() =>
            setTransform((t) => ({ ...t, scale: Math.max(0.2, t.scale * 0.8) }))
          }
        >
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={fitView}
        >
          <Maximize2 className="h-4 w-4" />
        </Button>
      </div>

      {/* SVG */}
      <svg
        ref={svgRef}
        className="w-full h-full"
        role="img"
        aria-label="Architecture diagram canvas"
        style={{ cursor: dragging ? "grabbing" : "grab" }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          <pattern
            id="dot-bg"
            x="0"
            y="0"
            width="20"
            height="20"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="2" cy="2" r="1" fill="#e2e8f0" />
          </pattern>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="10"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
          </marker>
        </defs>
        <rect width="100%" height="100%" fill="url(#dot-bg)" />

        <g
          transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}
        >
          {/* Edges */}
          {edges.map((edge) => {
            const src = nodeMap.get(edge.source_node_id)
            const tgt = nodeMap.get(edge.target_node_id)
            if (!src || !tgt) return null
            return (
              <g key={edge.id}>
                <path
                  d={edgePath(src, tgt)}
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="1.5"
                  markerEnd="url(#arrowhead)"
                />
                {edge.label && (
                  <text
                    x={
                      ((src.x_position ?? 0) + (tgt.x_position ?? 0)) / 2 +
                      NODE_WIDTH / 2
                    }
                    y={
                      ((src.y_position ?? 0) + (tgt.y_position ?? 0)) / 2 +
                      NODE_HEIGHT / 2
                    }
                    fontSize="10"
                    fill="#64748b"
                    textAnchor="middle"
                  >
                    {edge.label}
                  </text>
                )}
              </g>
            )
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const style = nodeStyleByType(node.node_type ?? "generic")
            const x = node.x_position ?? 0
            const y = node.y_position ?? 0
            const typeLabel = node.node_type
              ? node.node_type.charAt(0).toUpperCase() + node.node_type.slice(1)
              : "Generic"
            return (
              <g key={node.id}>
                <rect
                  x={x}
                  y={y}
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx="6"
                  ry="6"
                  fill={style.fill}
                  stroke={style.stroke}
                  strokeWidth="1.5"
                />
                <text
                  x={x + NODE_WIDTH / 2}
                  y={y + NODE_HEIGHT / 2 - 6}
                  fontSize="12"
                  fontWeight="600"
                  fill={style.textColor}
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {node.label}
                </text>
                <text
                  x={x + NODE_WIDTH / 2}
                  y={y + NODE_HEIGHT / 2 + 10}
                  fontSize="9"
                  fill="#64748b"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {typeLabel}
                  {node.provider && node.provider !== "generic"
                    ? ` · ${node.provider.toUpperCase()}`
                    : ""}
                </text>
              </g>
            )
          })}
        </g>
      </svg>

      {/* Status bar */}
      <div className="absolute bottom-2 left-3 text-xs text-muted-foreground bg-background/80 px-2 py-1 rounded">
        {nodes.length} nodes · {edges.length} edges ·{" "}
        {Math.round(transform.scale * 100)}%
      </div>

      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-muted-foreground">
            <Wand2 className="h-12 w-12 mx-auto mb-3 opacity-20" />
            <p className="text-sm">
              Enter a prompt and click Generate to create a diagram
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Left Panel ────────────────────────────────────────────────────────────────

function LeftPanel({
  projectTitle,
  projectId,
  initialPrompt,
  onGenerate,
  onRefine,
  isPending,
  versions,
  promptHistory,
}: {
  projectTitle: string
  projectId: string
  initialPrompt: string
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
      ProjectsService.updateProject({
        projectId,
        requestBody: { title },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] })
      toast.success("Title updated")
    },
    onError: () => toast.error("Failed to update title"),
  })

  useEffect(() => {
    setTitleValue(projectTitle)
  }, [projectTitle])

  useEffect(() => {
    setPrompt(initialPrompt)
  }, [initialPrompt])

  function handleTitleBlur() {
    setEditingTitle(false)
    if (titleValue.trim() && titleValue !== projectTitle) {
      updateTitleMutation.mutate(titleValue.trim())
    }
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-4 w-10 border-r bg-background">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(false)}
          title="Expand"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col w-72 border-r bg-background shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="text-sm font-semibold truncate">Project</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => setCollapsed(true)}
          title="Collapse"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {/* Title */}
          <div>
            <label
              htmlFor="project-title-input"
              className="text-xs text-muted-foreground uppercase tracking-wide"
            >
              Title
            </label>
            {editingTitle ? (
              <input
                id="project-title-input"
                className="w-full mt-1 text-sm font-medium border rounded px-2 py-1 bg-background"
                value={titleValue}
                onChange={(e) => setTitleValue(e.target.value)}
                onBlur={handleTitleBlur}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleTitleBlur()
                  if (e.key === "Escape") {
                    setEditingTitle(false)
                    setTitleValue(projectTitle)
                  }
                }}
              />
            ) : (
              <button
                type="button"
                className="w-full text-left mt-1 text-sm font-medium hover:text-primary transition-colors truncate"
                onClick={() => setEditingTitle(true)}
              >
                {titleValue || "Untitled Project"}
              </button>
            )}
          </div>

          <Separator />

          {/* Prompt */}
          <div className="space-y-2">
            <label
              htmlFor="arch-prompt"
              className="text-xs text-muted-foreground uppercase tracking-wide"
            >
              Architecture Prompt
            </label>
            <Textarea
              id="arch-prompt"
              placeholder="Describe your architecture... e.g. Azure hub and spoke with firewall, app gateway, AKS, and SQL"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="text-sm resize-none"
              rows={5}
            />
            <div className="flex gap-2">
              <Button
                className="flex-1"
                size="sm"
                onClick={() => onGenerate(prompt)}
                disabled={isPending || !prompt.trim()}
              >
                <Wand2 className="h-3.5 w-3.5 mr-1.5" />
                {isPending ? "Generating..." : "Generate"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={() => onRefine(prompt)}
                disabled={isPending || !prompt.trim()}
              >
                Refine
              </Button>
            </div>
          </div>

          <Separator />

          {/* Prompt history */}
          <CollapsibleSection title="Prompt History">
            {promptHistory.length === 0 ? (
              <p className="text-xs text-muted-foreground">No prompts yet.</p>
            ) : (
              <ul className="space-y-1">
                {promptHistory.map((p, i) => (
                  <li
                    key={i}
                    className="text-xs text-muted-foreground truncate"
                  >
                    {i + 1}. {p}
                  </li>
                ))}
              </ul>
            )}
          </CollapsibleSection>

          {/* Version history */}
          <CollapsibleSection title="Versions">
            {versions.length === 0 ? (
              <p className="text-xs text-muted-foreground">No versions yet.</p>
            ) : (
              <ul className="space-y-1">
                {versions.map((v) => (
                  <li key={v.id} className="text-xs text-muted-foreground">
                    v{v.version_number} ·{" "}
                    {v.created_at
                      ? new Date(v.created_at).toLocaleString()
                      : "Unknown"}
                  </li>
                ))}
              </ul>
            )}
          </CollapsibleSection>
        </div>
      </ScrollArea>
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

  function downloadMarkdown(content: string) {
    const blob = new Blob([content], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = "architecture-notes.md"
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function handleExportMarkdown() {
    try {
      const response = (await ProjectsService.exportMarkdown({
        projectId,
      })) as MarkdownExportResponse
      downloadMarkdown(response.content ?? notes)
    } catch {
      downloadMarkdown(notes)
    }
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center py-4 w-10 border-l bg-background">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(false)}
          title="Expand"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col w-80 border-l bg-background shrink-0">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <span className="text-sm font-semibold">Output</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={() => setCollapsed(true)}
          title="Collapse"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <Tabs defaultValue="components" className="flex-1 flex flex-col min-h-0">
        <TabsList className="mx-4 mt-2 shrink-0">
          <TabsTrigger value="components" className="flex-1 text-xs">
            Components ({components.length})
          </TabsTrigger>
          <TabsTrigger value="notes" className="flex-1 text-xs">
            Notes
          </TabsTrigger>
        </TabsList>

        <TabsContent value="components" className="flex-1 overflow-hidden mt-0">
          <ScrollArea className="h-full">
            <div className="p-4 space-y-3">
              {components.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Generate an architecture to see components.
                </p>
              ) : (
                components.map((c) => (
                  <div key={c.id} className="border rounded-md p-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium truncate">
                        {c.name}
                      </span>
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded-full shrink-0 ${componentBadgeClass(c.component_type ?? "")}`}
                      >
                        {c.component_type}
                      </span>
                    </div>
                    {c.provider && c.provider !== "generic" && (
                      <Badge variant="outline" className="text-xs">
                        {c.provider.toUpperCase()}
                      </Badge>
                    )}
                    {c.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2">
                        {c.description}
                      </p>
                    )}
                    {c.role_summary && (
                      <p className="text-xs text-muted-foreground italic line-clamp-2">
                        Role: {c.role_summary}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="notes" className="flex-1 overflow-hidden mt-0">
          <ScrollArea className="h-full">
            <div className="p-4">
              {!notes ? (
                <p className="text-sm text-muted-foreground text-center py-4">
                  Generate an architecture to see notes.
                </p>
              ) : (
                <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed text-foreground">
                  {notes}
                </pre>
              )}
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>

      {/* Export buttons */}
      <div className="p-4 border-t space-y-2">
        <p className="text-xs text-muted-foreground uppercase tracking-wide">
          Export
        </p>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 text-xs"
            onClick={handleExportMarkdown}
            disabled={!notes}
          >
            <FileText className="h-3 w-3 mr-1" />
            Markdown
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 text-xs"
            onClick={() => toast.info("SVG export coming soon")}
          >
            <Download className="h-3 w-3 mr-1" />
            SVG
          </Button>
        </div>
      </div>
    </div>
  )
}

// ─── Main Workspace ────────────────────────────────────────────────────────────

function ArchitectureWorkspace() {
  const { id } = Route.useParams()
  const queryClient = useQueryClient()

  const [nodes, setNodes] = useState<DiagramNodePublic[]>([])
  const [edges, setEdges] = useState<DiagramEdgePublic[]>([])
  const [components, setComponents] = useState<ComponentItemPublic[]>([])
  const [notes, setNotes] = useState("")
  const [promptHistory, setPromptHistory] = useState<string[]>([])

  // Fetch project
  const { data: project, isLoading } = useQuery({
    queryKey: ["project", id],
    queryFn: () => ProjectsService.readProject({ projectId: id }),
  })
  const { data: bundle } = useQuery({
    queryKey: ["project-bundle", id],
    queryFn: async () =>
      (await ProjectsService.exportBundle({
        projectId: id,
      })) as ProjectBundleResponse,
  })

  // Fetch versions
  const { data: versionsData } = useQuery({
    queryKey: ["project-versions", id],
    queryFn: () => ProjectsService.listVersions({ projectId: id }),
  })

  const versions: DiagramVersionPublic[] = versionsData?.data ?? []
  const currentPrompt = project?.current_prompt ?? ""

  const updateResult = useCallback(
    (result: {
      nodes: DiagramNodePublic[]
      edges: DiagramEdgePublic[]
      components: ComponentItemPublic[]
      diagram_version: DiagramVersionPublic
    }) => {
      setNodes(result.nodes)
      setEdges(result.edges)
      setComponents(result.components)
      setNotes(result.diagram_version.notes_markdown ?? "")
      queryClient.invalidateQueries({ queryKey: ["project", id] })
      queryClient.invalidateQueries({ queryKey: ["project-versions", id] })
    },
    [id, queryClient],
  )

  useEffect(() => {
    if (!bundle) return
    setNodes(bundle.nodes ?? [])
    setEdges(bundle.edges ?? [])
    setComponents(bundle.components ?? [])
    setNotes(bundle.diagram_version?.notes_markdown ?? "")

    const persistedPromptHistory =
      bundle.prompt_revisions?.map((revision) => revision.prompt_text) ?? []
    if (persistedPromptHistory.length > 0) {
      setPromptHistory(persistedPromptHistory)
      return
    }

    if (currentPrompt) {
      setPromptHistory([currentPrompt])
    }
  }, [bundle, currentPrompt])

  const generateMutation = useMutation({
    mutationFn: (req: GenerationRequest) =>
      ProjectsService.generateDiagram({ projectId: id, requestBody: req }),
    onSuccess: (data) => {
      updateResult(data)
      toast.success("Architecture generated!")
    },
    onError: () => toast.error("Generation failed"),
  })

  const refineMutation = useMutation({
    mutationFn: (req: GenerationRequest) =>
      ProjectsService.refineDiagram({ projectId: id, requestBody: req }),
    onSuccess: (data) => {
      updateResult(data)
      toast.success("Architecture refined!")
    },
    onError: () => toast.error("Refinement failed"),
  })

  const isPending = generateMutation.isPending || refineMutation.isPending

  function handleGenerate(prompt: string) {
    if (!prompt.trim()) return
    setPromptHistory((h) => [prompt, ...h.slice(0, 9)])
    generateMutation.mutate({
      prompt,
      cloud_context: project?.cloud_context ?? undefined,
      diagram_type: project?.diagram_type ?? undefined,
    })
  }

  function handleRefine(prompt: string) {
    if (!prompt.trim()) return
    setPromptHistory((h) => [prompt, ...h.slice(0, 9)])
    refineMutation.mutate({
      prompt,
      cloud_context: project?.cloud_context ?? undefined,
      diagram_type: project?.diagram_type ?? undefined,
    })
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-muted-foreground text-sm">Loading project...</div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-muted-foreground text-sm">Project not found.</div>
      </div>
    )
  }

  return (
    <div className="flex h-full overflow-hidden">
      <LeftPanel
        projectTitle={project.title ?? ""}
        projectId={id}
        initialPrompt={currentPrompt}
        onGenerate={handleGenerate}
        onRefine={handleRefine}
        isPending={isPending}
        versions={versions}
        promptHistory={promptHistory}
      />

      {/* Center: Diagram Canvas */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-4 py-2 border-b flex items-center gap-2">
          <span className="text-sm font-medium truncate">{project.title}</span>
          {project.cloud_context && (
            <Badge variant="outline" className="text-xs">
              {project.cloud_context}
            </Badge>
          )}
          {project.diagram_type && (
            <Badge variant="secondary" className="text-xs">
              {project.diagram_type}
            </Badge>
          )}
        </div>
        <div className="flex-1 relative">
          <DiagramCanvas nodes={nodes} edges={edges} />
        </div>
      </div>

      <RightPanel components={components} notes={notes} projectId={id} />
    </div>
  )
}
