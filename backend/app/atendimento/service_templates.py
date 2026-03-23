"""Serviço de templates de resposta para Atendimento."""
import logging
import re
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.atendimento.models import ResponseTemplate
from app.atendimento.schemas import ResponseTemplateIn, ResponseTemplateOut

logger = logging.getLogger(__name__)


async def list_templates(
    db: AsyncSession,
    user: User,
    category: str | None = None,
) -> list[ResponseTemplateOut]:
    """Lista templates do usuário, opcionalmente filtrados por categoria."""
    query = select(ResponseTemplate).where(ResponseTemplate.user_id == user.id)

    if category:
        query = query.where(ResponseTemplate.category == category)

    query = query.order_by(ResponseTemplate.name)
    result = await db.execute(query)
    templates = result.scalars().all()

    return [
        ResponseTemplateOut(
            id=t.id,
            name=t.name,
            text=t.text,
            category=t.category,
            variables=t.variables if isinstance(t.variables, list) else [],
            use_count=t.use_count,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in templates
    ]


async def get_template(
    db: AsyncSession,
    user: User,
    template_id: UUID,
) -> ResponseTemplateOut:
    """Obtém um template específico do usuário."""
    result = await db.execute(
        select(ResponseTemplate).where(
            and_(
                ResponseTemplate.id == template_id,
                ResponseTemplate.user_id == user.id,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise ValueError(f"Template {template_id} not found for user {user.id}")

    return ResponseTemplateOut(
        id=template.id,
        name=template.name,
        text=template.text,
        category=template.category,
        variables=template.variables if isinstance(template.variables, list) else [],
        use_count=template.use_count,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def create_template(
    db: AsyncSession,
    user: User,
    data: ResponseTemplateIn,
) -> ResponseTemplateOut:
    """Cria um novo template."""
    # Extrair variáveis do formato {variavel}
    variables = _extract_variables(data.text)

    # Verificar unicidade de nome por usuário
    existing = await db.execute(
        select(ResponseTemplate).where(
            and_(
                ResponseTemplate.user_id == user.id,
                ResponseTemplate.name == data.name,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Template with name '{data.name}' already exists for this user")

    template = ResponseTemplate(
        user_id=user.id,
        name=data.name,
        text=data.text,
        category=data.category,
        variables=variables,
        use_count=0,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    logger.info(
        "Template criado: user_id=%s name=%s variables=%s",
        user.id,
        data.name,
        variables,
    )

    return ResponseTemplateOut(
        id=template.id,
        name=template.name,
        text=template.text,
        category=template.category,
        variables=variables if isinstance(variables, list) else [],
        use_count=template.use_count,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def update_template(
    db: AsyncSession,
    user: User,
    template_id: UUID,
    data: ResponseTemplateIn,
) -> ResponseTemplateOut:
    """Atualiza um template existente."""
    result = await db.execute(
        select(ResponseTemplate).where(
            and_(
                ResponseTemplate.id == template_id,
                ResponseTemplate.user_id == user.id,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise ValueError(f"Template {template_id} not found for user {user.id}")

    # Verificar se novo nome já existe (exceto ele mesmo)
    if data.name != template.name:
        existing = await db.execute(
            select(ResponseTemplate).where(
                and_(
                    ResponseTemplate.user_id == user.id,
                    ResponseTemplate.name == data.name,
                    ResponseTemplate.id != template_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Template with name '{data.name}' already exists for this user")

    # Extrair variáveis do texto novo
    variables = _extract_variables(data.text)

    template.name = data.name
    template.text = data.text
    template.category = data.category
    template.variables = variables

    await db.commit()
    await db.refresh(template)

    logger.info(
        "Template atualizado: user_id=%s id=%s",
        user.id,
        template_id,
    )

    return ResponseTemplateOut(
        id=template.id,
        name=template.name,
        text=template.text,
        category=template.category,
        variables=variables if isinstance(variables, list) else [],
        use_count=template.use_count,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def delete_template(
    db: AsyncSession,
    user: User,
    template_id: UUID,
) -> None:
    """Deleta um template."""
    result = await db.execute(
        select(ResponseTemplate).where(
            and_(
                ResponseTemplate.id == template_id,
                ResponseTemplate.user_id == user.id,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise ValueError(f"Template {template_id} not found for user {user.id}")

    await db.delete(template)
    await db.commit()

    logger.info(
        "Template deletado: user_id=%s id=%s",
        user.id,
        template_id,
    )


async def use_template(
    db: AsyncSession,
    user: User,
    template_id: UUID,
) -> None:
    """Incrementa use_count de um template."""
    result = await db.execute(
        select(ResponseTemplate).where(
            and_(
                ResponseTemplate.id == template_id,
                ResponseTemplate.user_id == user.id,
            )
        )
    )
    template = result.scalar_one_or_none()

    if not template:
        raise ValueError(f"Template {template_id} not found for user {user.id}")

    template.use_count = (template.use_count or 0) + 1
    await db.commit()


def _extract_variables(text: str) -> list[str]:
    """Extrai nomes de variáveis do formato {variavel}."""
    pattern = r"\{([a-z_]+)\}"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(set(matches))  # Remove duplicatas


def fill_template(template_text: str, variables: dict[str, str]) -> str:
    """Preenche um template com valores de variáveis."""
    result = template_text
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", value)
    return result
