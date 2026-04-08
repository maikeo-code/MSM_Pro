"""
Regressão ciclo 529: garante que routers de atendimento fazem rethrow
de HTTPException antes do catch genérico.
"""
import inspect


def test_atendimento_router_rethrows_httpexception():
    """
    Todos os endpoints de templates em atendimento/router.py devem fazer
    'except HTTPException: raise' antes de 'except Exception:' para evitar
    que 404/400 internos virem 500 genéricos.
    """
    from app.atendimento import router as r

    src = inspect.getsource(r)
    # Conta quantos endpoints têm except Exception
    except_exception_count = src.count("except Exception as e:")
    rethrow_count = src.count("except HTTPException:")

    # Cada except Exception deve ser precedido por except HTTPException
    assert rethrow_count >= except_exception_count, (
        f"Faltam rethrows de HTTPException: "
        f"{except_exception_count} catchs genéricos, "
        f"{rethrow_count} rethrows."
    )
