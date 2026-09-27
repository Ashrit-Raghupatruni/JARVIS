import React from 'react'
import OAuthIntegrationsCard from '../OAuthIntegrationsCard'
import BluetoothProximityCard from '../BluetoothProximityCard'
import TelegramIntegrationCard from '../TelegramIntegrationCard'

interface IntegrationsSettingsTabProps {
  viewMode?: 'all' | 'oauth' | 'proximity' | 'telegram'
}

export const IntegrationsSettingsTab: React.FC<IntegrationsSettingsTabProps> = ({
  viewMode = 'all'
}) => {
  return (
    <div className="space-y-6">
      {(viewMode === 'all' || viewMode === 'telegram') && (
        <section>
          <TelegramIntegrationCard />
        </section>
      )}

      {(viewMode === 'all' || viewMode === 'oauth') && (
        <section>
          <OAuthIntegrationsCard />
        </section>
      )}

      {(viewMode === 'all' || viewMode === 'proximity') && (
        <section>
          <BluetoothProximityCard />
        </section>
      )}
    </div>
  )
}
export default IntegrationsSettingsTab
