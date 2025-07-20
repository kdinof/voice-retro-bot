#!/usr/bin/env python3
"""Reset all conversation states to IDLE for testing."""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.database_service import database_service


async def reset_all_sessions():
    """Reset all conversation states to IDLE."""
    print("🔄 Resetting all conversation states...")
    
    try:
        # Initialize database
        await database_service.initialize()
        print("✅ Database initialized")
        
        # Get session and repositories
        async for session in database_service.get_session():
            repos = await database_service.get_repositories(session)
            
            try:
                # Get all conversation states
                all_conversations = await repos.conversations.get_all()
                print(f"📊 Found {len(all_conversations)} conversation states")
                
                # Reset each conversation individually
                reset_count = 0
                for conv in all_conversations:
                    await repos.conversations.reset_conversation(conv.user_id)
                    reset_count += 1
                
                print(f"✅ Reset {reset_count} conversation states to IDLE")
                
                # Also clean up any expired states
                expired_count = await repos.conversations.cleanup_expired_states()
                if expired_count > 0:
                    print(f"🧹 Cleaned up {expired_count} expired states")
                
            finally:
                await repos.close()
        
        print("🎉 Session reset completed successfully!")
        
    except Exception as e:
        print(f"❌ Error resetting sessions: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("🚀 Voice Retro Bot - Session Reset")
    print("=" * 40)
    
    success = asyncio.run(reset_all_sessions())
    
    if success:
        print("\n✅ You can now run multiple retros for testing!")
    else:
        print("\n❌ Session reset failed. Check the error above.")