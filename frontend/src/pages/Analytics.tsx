import { TransactionVolumeChart, RiskDistributionChart, FraudTypeChart, FraudTrendChart } from '@/components/dashboard/Charts'

export function Analytics() {
  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold text-white">Analytics</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TransactionVolumeChart />
        <FraudTrendChart />
        <RiskDistributionChart />
        <FraudTypeChart />
      </div>
    </div>
  )
}
