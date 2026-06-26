export function Settings() {
  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold text-white">Settings</h1>
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <Setting label="API URL" value={import.meta.env.VITE_API_URL ?? 'http://localhost:8000'} />
        <Setting label="Mock Mode" value={import.meta.env.VITE_MOCK_MODE === 'true' ? 'Enabled' : 'Disabled (live API)'} />
        <Setting label="Live Feed Interval" value="4–7 seconds" />
        <Setting label="Max Feed Size" value="80 transactions" />
        <Setting label="Health Check Interval" value="30 seconds" />
        <Setting label="Feedback Stats Interval" value="60 seconds" />
      </div>
    </div>
  )
}

function Setting({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-200 font-mono bg-gray-800 px-2 py-0.5 rounded text-xs">{value}</span>
    </div>
  )
}
