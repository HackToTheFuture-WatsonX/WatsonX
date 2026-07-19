import { useEffect, useRef } from 'react'
import { io, Socket } from 'socket.io-client'

let _socket: Socket | null = null

function getSocket(): Socket {
  if (!_socket) {
    const port = (window as any).__V3_API_PORT__ ?? 8765
    _socket = io(`http://127.0.0.1:${port}`, {
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 10,
    })
  }
  return _socket
}

export function useSocket() {
  const socketRef = useRef<Socket>(getSocket())
  return socketRef.current
}

export function useSocketEvent<T = unknown>(
  event: string,
  handler: (data: T) => void,
  deps: React.DependencyList = [],
) {
  const socket = getSocket()
  useEffect(() => {
    socket.on(event, handler)
    return () => { socket.off(event, handler) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event, ...deps])
}
