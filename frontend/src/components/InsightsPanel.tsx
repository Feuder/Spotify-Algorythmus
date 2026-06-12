import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis } from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { PlaylistRun } from "@/types"

export function InsightsPanel({ run }: { run: PlaylistRun | null }) {
  const known = run?.tracks.filter((item) => !item.track.is_discovery).length ?? 0
  const discovery = run?.tracks.filter((item) => item.track.is_discovery).length ?? 0
  const bpmBuckets = [80, 100, 120, 140, 160].map((bpm) => ({
    bpm,
    count: run?.tracks.filter((item) => item.track.bpm && item.track.bpm >= bpm - 10 && item.track.bpm < bpm + 10).length ?? 0,
  }))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Hör-Insights</CardTitle>
        <CardDescription>Zusammensetzung des letzten Mixes</CardDescription>
      </CardHeader>
      <CardContent className="insights">
        <div className="chart-block">
          <span>Discovery-Verteilung</span>
          <ResponsiveContainer width="100%" height={145}>
            <PieChart>
              <Pie data={[{ name: "Bekannt", value: known }, { name: "Neu", value: discovery }]} dataKey="value" innerRadius={38} outerRadius={58} stroke="none" isAnimationActive={false}>
                <Cell fill="var(--success)" />
                <Cell fill="var(--primary)" />
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="chart-block">
          <span>BPM-Verteilung</span>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={bpmBuckets}>
              <XAxis dataKey="bpm" tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: "var(--secondary)" }} />
              <Bar dataKey="count" fill="var(--chart)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
