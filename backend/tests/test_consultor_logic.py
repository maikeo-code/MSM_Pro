"""Tests for Consultor module logic (schemas and input validation)."""
import os
import pytest
from datetime import datetime, timezone
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-32chars!")

from pydantic import ValidationError


class TestConsultorRequestSchema:
    """Test ConsultorRequest schema validation."""

    def test_consultor_request_minimal(self):
        """Test creating a minimal ConsultorRequest with no parameters."""
        from app.consultor.schemas import ConsultorRequest

        request = ConsultorRequest()
        assert request.mlb_id is None

    def test_consultor_request_with_mlb_id(self):
        """Test creating a ConsultorRequest with an mlb_id."""
        from app.consultor.schemas import ConsultorRequest

        mlb_id = "MLB123456789"
        request = ConsultorRequest(mlb_id=mlb_id)
        assert request.mlb_id == mlb_id

    def test_consultor_request_with_various_mlb_ids(self):
        """Test ConsultorRequest with different mlb_id formats."""
        from app.consultor.schemas import ConsultorRequest

        # Standard format
        request1 = ConsultorRequest(mlb_id="MLB123456789")
        assert request1.mlb_id == "MLB123456789"

        # With dash
        request2 = ConsultorRequest(mlb_id="MLB-123456789")
        assert request2.mlb_id == "MLB-123456789"

        # Numeric string
        request3 = ConsultorRequest(mlb_id="123456789")
        assert request3.mlb_id == "123456789"

    def test_consultor_request_mlb_id_empty_string(self):
        """Test that empty string mlb_id is accepted (treated as None-like)."""
        from app.consultor.schemas import ConsultorRequest

        # Empty string is allowed (optional field)
        request = ConsultorRequest(mlb_id="")
        assert request.mlb_id == ""

    def test_consultor_request_mlb_id_none_explicit(self):
        """Test explicitly passing None as mlb_id."""
        from app.consultor.schemas import ConsultorRequest

        request = ConsultorRequest(mlb_id=None)
        assert request.mlb_id is None

    def test_consultor_request_mlb_id_special_chars(self):
        """Test ConsultorRequest with special characters in mlb_id."""
        from app.consultor.schemas import ConsultorRequest

        # These should still be accepted (validation is lenient)
        request1 = ConsultorRequest(mlb_id="MLB_123@456")
        assert request1.mlb_id == "MLB_123@456"

        request2 = ConsultorRequest(mlb_id="MLB/123:456")
        assert request2.mlb_id == "MLB/123:456"


class TestConsultorResponseSchema:
    """Test ConsultorResponse schema validation."""

    def test_consultor_response_valid(self):
        """Test creating a valid ConsultorResponse."""
        from app.consultor.schemas import ConsultorResponse

        now = datetime.now(timezone.utc)
        response = ConsultorResponse(
            analise="Seu negócio está em crescimento. Recomendo aumentar a oferta.",
            anuncios_analisados=15,
            gerado_em=now,
        )

        assert response.analise == "Seu negócio está em crescimento. Recomendo aumentar a oferta."
        assert response.anuncios_analisados == 15
        assert response.gerado_em == now

    def test_consultor_response_long_analise(self):
        """Test ConsultorResponse with a long analise text."""
        from app.consultor.schemas import ConsultorResponse

        long_text = (
            "Este é um relatório completo da análise de seu negócio. "
            * 100  # Create a long text
        )
        response = ConsultorResponse(
            analise=long_text,
            anuncios_analisados=20,
            gerado_em=datetime.now(timezone.utc),
        )

        assert len(response.analise) > 1000
        assert response.anuncios_analisados == 20

    def test_consultor_response_zero_anuncios(self):
        """Test ConsultorResponse with zero anuncios_analisados."""
        from app.consultor.schemas import ConsultorResponse

        response = ConsultorResponse(
            analise="Nenhum anúncio foi analisado.",
            anuncios_analisados=0,
            gerado_em=datetime.now(timezone.utc),
        )

        assert response.anuncios_analisados == 0

    def test_consultor_response_many_anuncios(self):
        """Test ConsultorResponse with many anuncios_analisados."""
        from app.consultor.schemas import ConsultorResponse

        response = ConsultorResponse(
            analise="Análise de muitos anúncios completada.",
            anuncios_analisados=999,
            gerado_em=datetime.now(timezone.utc),
        )

        assert response.anuncios_analisados == 999

    def test_consultor_response_empty_analise(self):
        """Test ConsultorResponse with empty analise string."""
        from app.consultor.schemas import ConsultorResponse

        response = ConsultorResponse(
            analise="",
            anuncios_analisados=5,
            gerado_em=datetime.now(timezone.utc),
        )

        assert response.analise == ""

    def test_consultor_response_special_chars_in_analise(self):
        """Test ConsultorResponse with special characters in analise."""
        from app.consultor.schemas import ConsultorResponse

        special_text = "Analise: R$ 1.234,56 | +50% | @perfil | #hashtag | "
        response = ConsultorResponse(
            analise=special_text,
            anuncios_analisados=5,
            gerado_em=datetime.now(timezone.utc),
        )

        assert response.analise == special_text

    def test_consultor_response_gerado_em_now(self):
        """Test ConsultorResponse with current timestamp."""
        from app.consultor.schemas import ConsultorResponse

        before = datetime.now(timezone.utc)
        response = ConsultorResponse(
            analise="Teste",
            anuncios_analisados=1,
            gerado_em=datetime.now(timezone.utc),
        )
        after = datetime.now(timezone.utc)

        # The generated_em should be between before and after
        assert response.gerado_em >= before
        assert response.gerado_em <= after

    def test_consultor_response_gerado_em_past(self):
        """Test ConsultorResponse with a past timestamp."""
        from app.consultor.schemas import ConsultorResponse
        from datetime import timedelta

        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        response = ConsultorResponse(
            analise="Análise anterior",
            anuncios_analisados=10,
            gerado_em=past_time,
        )

        assert response.gerado_em == past_time

    def test_consultor_response_gerado_em_far_future(self):
        """Test ConsultorResponse with a far future timestamp."""
        from app.consultor.schemas import ConsultorResponse
        from datetime import timedelta

        future_time = datetime.now(timezone.utc) + timedelta(days=365)
        response = ConsultorResponse(
            analise="Análise futura",
            anuncios_analisados=5,
            gerado_em=future_time,
        )

        assert response.gerado_em == future_time

    def test_consultor_response_negative_anuncios(self):
        """Test that negative anuncios_analisados is accepted (no validation)."""
        from app.consultor.schemas import ConsultorResponse

        # The schema has no constraints on the int, so negative is technically allowed
        response = ConsultorResponse(
            analise="Erro: -1",
            anuncios_analisados=-1,
            gerado_em=datetime.now(timezone.utc),
        )

        assert response.anuncios_analisados == -1


class TestConsultorSchemasIntegration:
    """Integration tests combining request and response schemas."""

    def test_request_response_flow(self):
        """Test a request-response flow."""
        from app.consultor.schemas import ConsultorRequest, ConsultorResponse

        request = ConsultorRequest(mlb_id="MLB987654321")
        response = ConsultorResponse(
            analise="Anúncio analisado com sucesso.",
            anuncios_analisados=1,
            gerado_em=datetime.now(timezone.utc),
        )

        assert request.mlb_id == "MLB987654321"
        assert response.anuncios_analisados == 1

    def test_request_none_response_many(self):
        """Test request without mlb_id and response with many anuncios."""
        from app.consultor.schemas import ConsultorRequest, ConsultorResponse

        request = ConsultorRequest()  # No mlb_id, analyze all
        response = ConsultorResponse(
            analise="Todos os 50 anúncios analisados.",
            anuncios_analisados=50,
            gerado_em=datetime.now(timezone.utc),
        )

        assert request.mlb_id is None
        assert response.anuncios_analisados == 50

    def test_multiple_requests_same_response(self):
        """Test multiple requests with the same response schema."""
        from app.consultor.schemas import ConsultorRequest, ConsultorResponse

        requests = [
            ConsultorRequest(mlb_id=f"MLB{i}")
            for i in range(1000, 1005)
        ]
        response = ConsultorResponse(
            analise="5 anúncios analisados.",
            anuncios_analisados=5,
            gerado_em=datetime.now(timezone.utc),
        )

        assert len(requests) == 5
        assert response.anuncios_analisados == 5


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_consultor_request_very_long_mlb_id(self):
        """Test ConsultorRequest with a very long mlb_id."""
        from app.consultor.schemas import ConsultorRequest

        long_mlb = "MLB" + "1234567890" * 50  # Very long ID
        request = ConsultorRequest(mlb_id=long_mlb)
        assert request.mlb_id == long_mlb
        assert len(request.mlb_id) > 500

    def test_consultor_response_huge_analise(self):
        """Test ConsultorResponse with a huge analise text."""
        from app.consultor.schemas import ConsultorResponse

        huge_text = "X" * 100000  # 100KB of text
        response = ConsultorResponse(
            analise=huge_text,
            anuncios_analisados=1,
            gerado_em=datetime.now(timezone.utc),
        )

        assert len(response.analise) == 100000

    def test_consultor_response_unicode_in_analise(self):
        """Test ConsultorResponse with unicode characters in analise."""
        from app.consultor.schemas import ConsultorResponse

        unicode_text = (
            "Análise: 你好 мир 🚀 المتحدة اٹھار ελληνικά 🇧🇷"
        )
        response = ConsultorResponse(
            analise=unicode_text,
            anuncios_analisados=1,
            gerado_em=datetime.now(timezone.utc),
        )

        assert "🚀" in response.analise
        assert "🇧🇷" in response.analise

    def test_consultor_request_mlb_id_whitespace(self):
        """Test ConsultorRequest with whitespace in mlb_id."""
        from app.consultor.schemas import ConsultorRequest

        # Whitespace is preserved (no stripping)
        request = ConsultorRequest(mlb_id="  MLB123  ")
        assert request.mlb_id == "  MLB123  "

    def test_consultor_response_multiline_analise(self):
        """Test ConsultorResponse with multiline analise text."""
        from app.consultor.schemas import ConsultorResponse

        multiline_text = """Linha 1
Linha 2
Linha 3
- Ponto 1
- Ponto 2"""

        response = ConsultorResponse(
            analise=multiline_text,
            anuncios_analisados=3,
            gerado_em=datetime.now(timezone.utc),
        )

        assert "\n" in response.analise
        assert "Linha 1" in response.analise
        assert "Ponto 1" in response.analise

    def test_consultor_response_very_large_anuncios_count(self):
        """Test ConsultorResponse with very large anuncios_analisados."""
        from app.consultor.schemas import ConsultorResponse

        huge_count = 999999999
        response = ConsultorResponse(
            analise="Muitos anúncios analisados.",
            anuncios_analisados=huge_count,
            gerado_em=datetime.now(timezone.utc),
        )

        assert response.anuncios_analisados == huge_count

    def test_consultor_request_response_timezone_utc(self):
        """Test that ConsultorResponse preserves UTC timezone."""
        from app.consultor.schemas import ConsultorResponse

        utc_time = datetime(2026, 3, 26, 12, 30, 45, tzinfo=timezone.utc)
        response = ConsultorResponse(
            analise="Teste",
            anuncios_analisados=1,
            gerado_em=utc_time,
        )

        assert response.gerado_em.tzinfo == timezone.utc
        assert response.gerado_em.hour == 12
        assert response.gerado_em.minute == 30


class TestConsultorResponseSerialization:
    """Test schema serialization to dict/JSON."""

    def test_response_model_dump(self):
        """Test that ConsultorResponse can be serialized to dict."""
        from app.consultor.schemas import ConsultorResponse

        now = datetime.now(timezone.utc)
        response = ConsultorResponse(
            analise="Teste de serialização",
            anuncios_analisados=10,
            gerado_em=now,
        )

        # model_dump is Pydantic v2 method
        response_dict = response.model_dump()
        assert response_dict["analise"] == "Teste de serialização"
        assert response_dict["anuncios_analisados"] == 10
        assert response_dict["gerado_em"] == now

    def test_request_model_dump(self):
        """Test that ConsultorRequest can be serialized to dict."""
        from app.consultor.schemas import ConsultorRequest

        request = ConsultorRequest(mlb_id="MLB999")
        request_dict = request.model_dump()
        assert request_dict["mlb_id"] == "MLB999"

    def test_response_model_dump_none_values(self):
        """Test serialization of response with various values."""
        from app.consultor.schemas import ConsultorResponse

        response = ConsultorResponse(
            analise="",  # Empty string
            anuncios_analisados=0,
            gerado_em=datetime.now(timezone.utc),
        )

        response_dict = response.model_dump()
        assert response_dict["analise"] == ""
        assert response_dict["anuncios_analisados"] == 0
