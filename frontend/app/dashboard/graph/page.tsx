"use client"

import * as React from "react"
import { Network, RefreshCw, Share2, ZoomIn, Info, Loader2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useTenantContext } from "@/lib/tenant-context"
import { getGraphData, rebuildGraph } from "@/lib/api"
// Dynamically import ForceGraph to avoid SSR issues
import dynamic from 'next/dynamic'

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false })

export default function KnowledgeGraphPage() {
  const { activeTenant } = useTenantContext()
  const [graphData, setGraphData] = React.useState<any>(null)
  const [loading, setLoading] = React.useState(false)
  const [generating, setGenerating] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  // Store ref to the graph instance for zooming
  const fgRef = React.useRef<any>(null)

  const fetchGraph = React.useCallback(async () => {
    if (!activeTenant) return
    setLoading(true)
    setError(null)
    try {
      const data = await getGraphData(activeTenant.bot_id)
      if (data && data.nodes && data.nodes.length > 0) {
        // Map data to match react-force-graph expectations (source/target instead of from/to)
        const mappedData = {
          nodes: data.nodes.map((n: any) => ({ ...n, val: 20 })), // default size
          links: data.edges.map((e: any) => ({
            source: e.from,
            target: e.to,
            label: e.label
          }))
        }
        setGraphData(mappedData)
      } else {
        setGraphData(null)
      }
    } catch (e) {
      setError("Failed to load knowledge network.")
    } finally {
      setLoading(false)
    }
  }, [activeTenant])

  const generateGraph = async () => {
    if (!activeTenant) return
    setGenerating(true)
    setError(null)
    try {
      const res = await rebuildGraph(activeTenant.bot_id)
      if (res.status === "accepted") {
        // Background task started, wait then poll
        setTimeout(fetchGraph, 7000)
      } else {
        setError("Failed to trigger graph generation.")
      }
    } catch (e) {
      setError("Error communicating with intelligence engine.")
    } finally {
      setGenerating(false)
    }
  }

  React.useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  const zoomToFit = () => {
    if (fgRef.current) {
      fgRef.current.zoomToFit(400, 20)
    }
  }

  // Node drawing logic to match the pill-shape from the video
  const paintNode = React.useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.label || node.id;
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px "Inter", sans-serif`;
    const textWidth = ctx.measureText(label).width;
    const bckgDimensions = [textWidth + fontSize * 2, fontSize + fontSize * 1.5]; // some padding

    // Determine color based on node type/degree (mocked here for aesthetics)
    // Root or central nodes get purple, others get teal or green
    const color = node.id.includes("Lecture") || node.id.includes("DBMS") 
        ? "#5b21b6"  // Deep Purple
        : "#0d9488"; // Teal

    ctx.fillStyle = color;
    
    // Draw pill shape
    const radius = bckgDimensions[1] / 2;
    const x = node.x - bckgDimensions[0] / 2;
    const y = node.y - bckgDimensions[1] / 2;
    const w = bckgDimensions[0];
    const h = bckgDimensions[1];

    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    ctx.lineTo(x + radius, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    ctx.fill();

    // Node Border
    ctx.strokeStyle = "rgba(255,255,255,0.4)";
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();

    // Text Label
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ffffff';
    ctx.fillText(label, node.x, node.y);

    // Save bounding box for hover hit-testing
    node.__bckgDimensions = bckgDimensions; 
  }, []);

  const pointerArea = React.useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
      const bckgDimensions = node.__bckgDimensions;
      if (!bckgDimensions) return;
      const bckgW = bckgDimensions[0];
      const bckgH = bckgDimensions[1];
      
      ctx.fillStyle = color;
      
      const radius = bckgH / 2;
      const x = node.x - bckgW / 2;
      const y = node.y - bckgH / 2;
      const w = bckgW;
      const h = bckgH;

      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.lineTo(x + w - radius, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
      ctx.lineTo(x + w, y + h - radius);
      ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
      ctx.lineTo(x + radius, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
      ctx.lineTo(x, y + radius);
      ctx.quadraticCurveTo(x, y, x + radius, y);
      ctx.closePath();
      ctx.fill();
  }, []);

  if (!activeTenant) {
    return (
      <div className="py-2">
        <h1 className="text-2xl font-semibold">Knowledge Graph</h1>
        <Alert className="mt-6" variant="destructive">
          <AlertTitle>Select a bot first</AlertTitle>
          <AlertDescription>Choose a bot from the sidebar to visualize its intelligence network.</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 py-2">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Knowledge Network</h1>
          <p className="text-sm text-muted-foreground">
            Visualizing dynamic semantic relations for <span className="font-medium text-foreground">{activeTenant.name}</span>
          </p>
        </div>
        <div className="flex gap-2">
           <Button variant="outline" size="sm" onClick={fetchGraph} disabled={loading}>
             <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
             Refresh
           </Button>
           <Button size="sm" onClick={generateGraph} disabled={generating || loading}>
             {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Network className="mr-2 h-4 w-4" />}
             {graphData ? "Rebuild Graph" : "Generate Graph"}
           </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-3 overflow-hidden border-none shadow-2xl bg-white backdrop-blur-xl relative h-[700px]">
           <CardHeader className="absolute top-0 w-full z-10 border-b border-gray-200 bg-white/80 backdrop-blur-sm">
             <div className="flex items-center justify-between">
               <CardTitle className="text-lg text-slate-800 font-bold flex items-center gap-2">
                 <div className="h-2 w-2 rounded-full bg-teal-500 animate-pulse" />
                 Relational Hub
               </CardTitle>
               <div className="flex gap-1">
                  <div onClick={zoomToFit} className="h-8 w-8 rounded bg-slate-100 flex items-center justify-center cursor-pointer hover:bg-slate-200 transition-colors shadow-sm">
                    <ZoomIn className="h-4 w-4 text-slate-600" />
                  </div>
               </div>
             </div>
           </CardHeader>
           
           <CardContent className="p-0 h-full w-full bg-[#f8fafc]">
              {loading ? (
                <div className="h-full flex flex-col items-center justify-center gap-4 text-slate-500">
                  <Loader2 className="h-10 w-10 animate-spin text-teal-500" />
                  <p className="font-medium">Syncing Network Nodes...</p>
                </div>
              ) : graphData ? (
                <div className="h-full w-full pt-[70px]">
                    <ForceGraph2D
                      ref={fgRef}
                      graphData={graphData}
                      nodeCanvasObject={paintNode}
                      nodePointerAreaPaint={pointerArea}
                      linkColor={() => "#94a3b8"}
                      linkWidth={2}
                      linkDirectionalParticles={2}
                      linkDirectionalParticleSpeed={0.005}
                      linkDirectionalParticleWidth={4}
                      linkCurvature={0.2}
                      backgroundColor="#f8fafc"
                      width={undefined}
                      height={undefined}
                    />
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center gap-6 text-center max-w-md mx-auto px-6">
                   <div className="h-20 w-20 rounded-full bg-teal-500/10 flex items-center justify-center border border-teal-500/20">
                      <Network className="h-10 w-10 text-teal-500" />
                   </div>
                   <div>
                      <h3 className="text-xl font-bold text-slate-800 mb-2">No Knowledge Map Generated</h3>
                      <p className="text-slate-500 text-sm leading-relaxed">
                        The intelligence engine hasn't parsed your documents into a relational network yet. 
                        Click "Generate Graph" to build your semantic hub.
                      </p>
                   </div>
                   <Button onClick={generateGraph} className="bg-teal-600 hover:bg-teal-700 text-white border-none px-8">
                     Build Intelligence Network
                   </Button>
                </div>
              )}
           </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
           <Card className="bg-white border-gray-200 shadow-sm">
             <CardHeader>
               <CardTitle className="text-sm font-bold flex items-center gap-2 text-slate-800">
                 <Info className="h-4 w-4 text-teal-600" />
                 Intelligence Specs
               </CardTitle>
             </CardHeader>
             <CardContent className="space-y-4">
                <div className="flex justify-between items-center border-b border-slate-100 pb-2">
                   <span className="text-xs text-slate-500">Provider</span>
                   <span className="text-xs font-bold text-slate-800 uppercase italic tracking-tighter">Force Graph 2D</span>
                </div>
                <div className="flex justify-between items-center border-b border-slate-100 pb-2">
                   <span className="text-xs text-slate-500">Architecture</span>
                   <span className="text-xs font-bold text-slate-800 italic tracking-tighter">Dynamic NetworkX</span>
                </div>
                <div className="space-y-1 pt-2">
                   <p className="text-[10px] text-slate-400 uppercase font-black">Optimization Tips</p>
                   <p className="text-xs text-slate-600 leading-relaxed">
                     Well-structured PDFs and Markdown files result in denser, more interconnected graphs. Use the mouse to drag nodes and scroll to zoom.
                   </p>
                </div>
             </CardContent>
           </Card>

           <Alert className="bg-teal-50 border-teal-200 text-teal-800">
             <Info className="h-4 w-4" />
             <AlertTitle className="text-xs font-bold">Network Insight</AlertTitle>
             <AlertDescription className="text-[10px] opacity-90 leading-relaxed mt-1">
               The graph visualizes how information segments link together dynamically. Highly connected nodes represent "Single Source of Truth" clusters in your data.
             </AlertDescription>
           </Alert>
        </div>
      </div>
    </div>
  )
}

