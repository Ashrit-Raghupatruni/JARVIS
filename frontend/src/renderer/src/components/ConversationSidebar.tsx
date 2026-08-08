import React, { useState, useEffect } from 'react'
import { MessageSquare, Plus, Edit2, Trash2, Check, X, Clock } from 'lucide-react'

export interface ConversationItem {
  id: string
  title: string
  created_at: string | null
  updated_at: string | null
  message_count?: number
}

interface ConversationSidebarProps {
  activeId: string | null
  onSelectConversation: (id: string) => void
  onNewChat: () => void
}

const getApiUrl = (path: string) => {
  const host = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1' && window.location.hostname !== '' ? window.location.hostname : '127.0.0.1'
  return `http://${host}:8000${path}`
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  activeId,
  onSelectConversation,
  onNewChat,
}) => {
  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [loading, setLoading] = useState<boolean>(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState<string>('')

  const fetchConversations = async () => {
    setLoading(true)
    try {
      const res = await fetch(getApiUrl('/api/conversations'))
      if (res.ok) {
        const data = await res.json()
        if (data.conversations) {
          setConversations(data.conversations)
        }
      }
    } catch (e) {
      console.error('Failed to load conversations:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConversations()
  }, [activeId])

  const handleStartRename = (conv: ConversationItem, e: React.MouseEvent) => {
    e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title)
  }

  const handleSaveRename = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!editTitle.trim()) return
    try {
      const res = await fetch(getApiUrl(`/api/conversations/${id}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle.trim() }),
      })
      if (res.ok) {
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, title: editTitle.trim() } : c))
        )
      }
    } catch (err) {
      console.error('Failed to rename conversation:', err)
    } finally {
      setEditingId(null)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this conversation?')) return
    try {
      const res = await fetch(getApiUrl(`/api/conversations/${id}`), {
        method: 'DELETE',
      })
      if (res.ok) {
        setConversations((prev) => prev.filter((c) => c.id !== id))
        if (activeId === id) {
          onNewChat()
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  return (
    <div className="w-64 bg-slate-900/90 border-r border-cyan-500/20 flex flex-col h-full text-slate-200">
      {/* Header & New Chat */}
      <div className="p-3 border-b border-cyan-500/20 flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wider text-cyan-400 uppercase flex items-center gap-1.5">
          <MessageSquare className="w-4 h-4 text-cyan-400" />
          History
        </span>
        <button
          onClick={onNewChat}
          className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-cyan-300 bg-cyan-950/60 hover:bg-cyan-900/80 border border-cyan-500/30 rounded transition-all shadow-sm"
        >
          <Plus className="w-3.5 h-3.5" />
          New
        </button>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading && conversations.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-400">Loading history...</div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500">No past conversations</div>
        ) : (
          conversations.map((conv) => {
            const isActive = activeId === conv.id
            const isEditing = editingId === conv.id

            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`group relative flex items-center justify-between p-2 rounded-lg cursor-pointer text-xs transition-all border ${
                  isActive
                    ? 'bg-cyan-950/70 border-cyan-500/40 text-cyan-200 shadow-sm'
                    : 'bg-slate-800/40 border-transparent hover:bg-slate-800/80 hover:border-slate-700 text-slate-300'
                }`}
              >
                {isEditing ? (
                  <div className="flex items-center gap-1 w-full" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full bg-slate-950 border border-cyan-500/50 rounded px-1.5 py-0.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-400"
                      autoFocus
                    />
                    <button
                      onClick={(e) => handleSaveRename(conv.id, e)}
                      className="p-1 hover:text-green-400 text-slate-400"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setEditingId(null)
                      }}
                      className="p-1 hover:text-red-400 text-slate-400"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex flex-col min-w-0 pr-2">
                      <span className="truncate font-medium">{conv.title}</span>
                      <span className="text-[10px] text-slate-500 flex items-center gap-1 mt-0.5">
                        <Clock className="w-2.5 h-2.5" />
                        {conv.created_at
                          ? new Date(conv.created_at).toLocaleDateString([], {
                              month: 'short',
                              day: 'numeric',
                            })
                          : 'Recent'}
                      </span>
                    </div>

                    {/* Actions on hover */}
                    <div className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
                      <button
                        onClick={(e) => handleStartRename(conv, e)}
                        title="Rename"
                        className="p-1 hover:text-cyan-300 text-slate-400"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(conv.id, e)}
                        title="Delete"
                        className="p-1 hover:text-rose-400 text-slate-400"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
