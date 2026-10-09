import { Button } from "@doc-anonymizer/ui/primitives/button";

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <h1 className="text-lg font-semibold">文档脱敏工具</h1>
      <Button id="run" disabled>开始脱敏</Button>
    </div>
  );
}
