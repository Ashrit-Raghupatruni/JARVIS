import React from 'react'
import OAuthIntegrationsCard from '../OAuthIntegrationsCard'
import BluetoothProximityCard from '../BluetoothProximityCard'

interface IntegrationsSettingsTabProps {
  viewMode?: 'all' | 'oauth' | 'proximity'
}

export const IntegrationsSettingsTab: React.FC<IntegrationsSettingsTabProps> = ({
  viewMode = 'all'
}) => {
  return (
    <div className="space-y-6">
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
