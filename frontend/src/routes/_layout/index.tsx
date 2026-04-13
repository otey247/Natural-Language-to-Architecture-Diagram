import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import {
  Calendar,
  FolderOpen,
  LayoutGrid,
  MoreHorizontal,
  Plus,
  Trash2,
} from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { ProjectsService } from "@/client"
import type { ProjectCreate, ProjectPublic } from "@/client/types.gen"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const Route = createFileRoute("/_layout/")({
  component: ProjectsDashboard,
  head: () => ({
    meta: [{ title: "Architecture Projects" }],
  }),
})

const CLOUD_CONTEXTS = [
  "Azure",
  "AWS",
  "GCP",
  "Multi-Cloud",
  "On-Premises",
  "Hybrid",
]
const DIAGRAM_TYPES = ["Conceptual", "Logical", "Deployment"]

function NewProjectDialog() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<ProjectCreate>({
    title: "",
    description: "",
    cloud_context: undefined,
    diagram_type: undefined,
  })

  const createMutation = useMutation({
    mutationFn: (data: ProjectCreate) =>
      ProjectsService.createProject({ requestBody: data }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast.success("Project created")
      setOpen(false)
      setForm({
        title: "",
        description: "",
        cloud_context: undefined,
        diagram_type: undefined,
      })
    },
    onError: () => toast.error("Failed to create project"),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim()) return
    createMutation.mutate({
      ...form,
      description: form.description || null,
      cloud_context: form.cloud_context || null,
      diagram_type: form.diagram_type || null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>New Architecture Project</DialogTitle>
          <DialogDescription>
            Create a new project to start designing your architecture.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title *</Label>
            <Input
              id="title"
              value={form.title}
              onChange={(e) =>
                setForm((f) => ({ ...f, title: e.target.value }))
              }
              placeholder="My Architecture Project"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              value={form.description ?? ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
              placeholder="Brief description of the project"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cloud_context">Cloud Context</Label>
            <Select
              value={form.cloud_context ?? ""}
              onValueChange={(v) =>
                setForm((f) => ({ ...f, cloud_context: v || null }))
              }
            >
              <SelectTrigger id="cloud_context">
                <SelectValue placeholder="Select cloud context" />
              </SelectTrigger>
              <SelectContent>
                {CLOUD_CONTEXTS.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="diagram_type">Diagram Type</Label>
            <Select
              value={form.diagram_type ?? ""}
              onValueChange={(v) =>
                setForm((f) => ({ ...f, diagram_type: v || null }))
              }
            >
              <SelectTrigger id="diagram_type">
                <SelectValue placeholder="Select diagram type" />
              </SelectTrigger>
              <SelectContent>
                {DIAGRAM_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || !form.title.trim()}
            >
              {createMutation.isPending ? "Creating…" : "Create Project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ProjectCard({ project }: { project: ProjectPublic }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => ProjectsService.deleteProject({ projectId: project.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast.success("Project deleted")
    },
    onError: () => toast.error("Failed to delete project"),
  })

  const duplicateMutation = useMutation({
    mutationFn: () =>
      ProjectsService.duplicateProject({ projectId: project.id }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      toast.success("Project duplicated")
    },
    onError: () => toast.error("Failed to duplicate project"),
  })

  const updatedAt = project.updated_at
    ? new Date(project.updated_at).toLocaleDateString()
    : project.created_at
      ? new Date(project.created_at).toLocaleDateString()
      : "—"

  return (
    <Card className="flex flex-col hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base line-clamp-2 leading-snug">
            {project.title}
          </CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0">
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">More</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() =>
                  navigate({ to: "/projects/$id", params: { id: project.id } })
                }
              >
                <FolderOpen className="mr-2 h-4 w-4" />
                Open
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => duplicateMutation.mutate()}
                disabled={duplicateMutation.isPending}
              >
                <LayoutGrid className="mr-2 h-4 w-4" />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {project.description && (
          <CardDescription className="line-clamp-2 text-sm">
            {project.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="pb-2 flex-1">
        <div className="flex flex-wrap gap-1">
          {project.cloud_context && (
            <Badge variant="secondary" className="text-xs">
              {project.cloud_context}
            </Badge>
          )}
          {project.diagram_type && (
            <Badge variant="outline" className="text-xs">
              {project.diagram_type}
            </Badge>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex items-center justify-between pt-2 border-t">
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3" />
          <span>{updatedAt}</span>
        </div>
        <Button
          size="sm"
          variant="default"
          onClick={() =>
            navigate({ to: "/projects/$id", params: { id: project.id } })
          }
        >
          Open
        </Button>
      </CardFooter>
    </Card>
  )
}

function ProjectsDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => ProjectsService.listProjects({ skip: 0, limit: 100 }),
  })

  const projects = data?.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Architecture Projects
          </h1>
          <p className="text-muted-foreground">
            Design and manage your cloud architecture diagrams
          </p>
        </div>
        <NewProjectDialog />
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="h-48 animate-pulse bg-muted" />
          ))}
        </div>
      )}

      {!isLoading && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center text-center py-20 gap-4">
          <div className="rounded-full bg-muted p-6">
            <LayoutGrid className="h-10 w-10 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">No projects yet</h3>
            <p className="text-muted-foreground">
              Create your first architecture project to get started
            </p>
          </div>
          <NewProjectDialog />
        </div>
      )}

      {!isLoading && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  )
}
