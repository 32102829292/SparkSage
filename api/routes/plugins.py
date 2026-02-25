from fastapi import APIRouter, Depends
from api.deps import get_current_user
import plugins.loader as plugin_loader

router = APIRouter()


@router.get("")
async def list_plugins(user=Depends(get_current_user)):
    return plugin_loader.list_plugins()


@router.post("/{name}/enable")
async def enable_plugin(name: str, user=Depends(get_current_user)):
    plugin_loader.enable_plugin(name)
    return {"name": name, "enabled": True}


@router.post("/{name}/disable")
async def disable_plugin(name: str, user=Depends(get_current_user)):
    plugin_loader.disable_plugin(name)
    return {"name": name, "enabled": False}