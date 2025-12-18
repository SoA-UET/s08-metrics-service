from flask_socketio import SocketIO
from typing import Callable


class Streaming:
    """A class to encapsulate SocketIO streaming API handlers."""
    
    def __init__(self, event: str, handler: Callable, namespace: str = '/'):
        """
        Initialize a streaming API handler.
        
        Args:
            event: The SocketIO event name to listen for
            handler: The handler function to execute when the event is received
            namespace: The SocketIO namespace (default: '/')
        """
        self.event = event
        self.handler = handler
        self.namespace = namespace
    
    def register(self, socketio: SocketIO):
        """
        Register this streaming API with the SocketIO instance.
        
        Args:
            socketio: The SocketIO instance to register with
        """
        socketio.on_event(self.event, self.handler, namespace=self.namespace)
