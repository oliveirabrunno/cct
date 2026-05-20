"""
Testes para _is_tennis_relevant() — validação de conteúdo de imagem.

Garante que apenas imagens de tênis (atletas, quadras, torneios) passam,
e que paisagens, natureza, e imagens genéricas são rejeitadas.
"""

import pytest
import sys
import os

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.image_sources.google_images import (
    _is_tennis_relevant,
    _is_safe_image,
    TRUSTED_DOMAINS,
    BLOCKED_KEYWORDS,
    _TENNIS_KEYWORDS,
)


class TestIsTennisRelevant:
    """Testes para a função _is_tennis_relevant()."""

    # ── Domínios confiáveis devem SEMPRE passar ──────────────────────────

    def test_trusted_domain_atptour(self):
        """Imagem do atptour.com deve passar sem validação de título."""
        assert _is_tennis_relevant(
            url="https://www.atptour.com/photos/alcaraz.jpg",
            title="Random image with no context",
            source="ATP Tour",
            player_name="Carlos Alcaraz",
        )

    def test_trusted_domain_flickr(self):
        """Flickr é confiável (já tem _name_ok no módulo de Flickr)."""
        assert _is_tennis_relevant(
            url="https://farm66.staticflickr.com/65535/12345.jpg",
            title="Some photo",
            source="Flickr",
            player_name="Jannik Sinner",
        )

    def test_trusted_domain_reuters(self):
        """Reuters é fonte confiável de imagens editoriais."""
        assert _is_tennis_relevant(
            url="https://www.reuters.com/resizer/some-image.jpg",
            title="",
            source="Reuters",
            player_name="Novak Djokovic",
        )

    def test_trusted_domain_gettyimages(self):
        assert _is_tennis_relevant(
            url="https://media.gettyimages.com/some-photo.jpg",
            title="",
            source="Getty Images",
            player_name="Rafael Nadal",
        )

    def test_trusted_domain_wimbledon(self):
        assert _is_tennis_relevant(
            url="https://www.wimbledon.com/images/player.jpg",
            title="",
            source="Wimbledon",
            player_name="Andy Murray",
        )

    # ── Imagens com contexto de tênis + sobrenome devem PASSAR ───────────

    def test_tennis_keyword_and_surname_in_title(self):
        """Título com keyword de tênis + sobrenome do jogador → aceita."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Alcaraz wins Roland Garros semifinal 2026",
            source="Sports News",
            player_name="Carlos Alcaraz",
        )

    def test_tennis_keyword_in_source_surname_in_title(self):
        """Keyword no source, sobrenome no título → aceita."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Sinner in action at the court",
            source="Tennis World USA",
            player_name="Jannik Sinner",
        )

    def test_atp_keyword(self):
        """ATP como keyword de tênis."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Djokovic ATP Masters 1000",
            source="Sport Blog",
            player_name="Novak Djokovic",
        )

    def test_tournament_name_as_keyword(self):
        """Nome de torneio conhecido como keyword de tênis."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Fonseca estreia em Roma",
            source="Blog Esportivo",
            player_name="João Fonseca",
        )

    # ── Paisagens e imagens genéricas devem ser REJEITADAS ────────────────

    def test_landscape_no_tennis_context(self):
        """Paisagem sem nenhum contexto de tênis → rejeita."""
        assert not _is_tennis_relevant(
            url="https://wallpapers.com/beautiful-sunset.jpg",
            title="Beautiful sunset over the mountains",
            source="Wallpapers HD",
            player_name="Carlos Alcaraz",
        )

    def test_generic_image_no_surname(self):
        """Imagem genérica sem sobrenome nem keyword de tênis → rejeita."""
        assert not _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Amazing sports action shot",
            source="Stock Photos",
            player_name="Jannik Sinner",
        )

    def test_tennis_keyword_but_no_surname(self):
        """Keyword de tênis presente mas sobrenome ausente → rejeita."""
        assert not _is_tennis_relevant(
            url="https://randomsite.com/photo.jpg",
            title="Tennis court in the sunset",
            source="Photography Blog",
            player_name="Carlos Alcaraz",
        )

    def test_surname_but_no_tennis_context(self):
        """Sobrenome presente mas sem keyword de tênis → rejeita."""
        assert not _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Alcaraz family vacation in Spain",
            source="Travel Blog",
            player_name="Carlos Alcaraz",
        )

    def test_empty_url_rejected(self):
        """URL vazia → rejeita."""
        assert not _is_tennis_relevant(
            url="",
            title="Alcaraz tennis",
            source="ATP",
            player_name="Carlos Alcaraz",
        )

    # ── Casos de borda ───────────────────────────────────────────────────

    def test_short_surname_skips_name_check(self):
        """Sobrenome curto (< 3 chars) não exige match no título."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Tennis action at Wimbledon",
            source="BBC Sport",
            player_name="Li Na",
        )

    def test_empty_player_name(self):
        """Sem player_name → só exige keyword de tênis."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="Tennis match at Roland Garros",
            source="L'Equipe",
            player_name="",
        )

    def test_case_insensitive(self):
        """Match deve ser case-insensitive."""
        assert _is_tennis_relevant(
            url="https://example.com/photo.jpg",
            title="ALCARAZ WINS TENNIS MATCH",
            source="SPORTS",
            player_name="Carlos Alcaraz",
        )


class TestIsSafeImage:
    """Testes para confirmar que keywords de paisagem são bloqueadas."""

    def test_landscape_keyword_blocked(self):
        assert not _is_safe_image(
            url="https://example.com/landscape.jpg",
            title="Beautiful landscape",
            source="Wallpapers",
        )

    def test_mountain_keyword_blocked(self):
        assert not _is_safe_image(
            url="https://example.com/photo.jpg",
            title="Mountain sunset panorama",
            source="Nature Photography",
        )

    def test_wallpaper_keyword_blocked(self):
        assert not _is_safe_image(
            url="https://example.com/photo.jpg",
            title="HD wallpaper download",
            source="Wallpapers",
        )

    def test_tennis_image_passes_safe_check(self):
        assert _is_safe_image(
            url="https://example.com/photo.jpg",
            title="Alcaraz wins Roland Garros",
            source="Tennis World",
        )


class TestBlockedKeywordsComplete:
    """Verifica que as keywords de paisagem foram adicionadas."""

    def test_landscape_keywords_present(self):
        landscape_words = {
            "landscape", "mountain", "sunset", "sunrise", "beach",
            "ocean", "forest", "nature", "skyline", "scenery",
            "panorama", "aerial", "drone", "cityscape", "wallpaper",
        }
        for word in landscape_words:
            assert word in BLOCKED_KEYWORDS, f"'{word}' deveria estar em BLOCKED_KEYWORDS"


class TestTrustedDomains:
    """Verifica que domínios essenciais estão na whitelist."""

    def test_essential_domains_present(self):
        essential = {
            "atptour.com", "wtatennis.com",
            "rolandgarros.com", "wimbledon.com",
            "gettyimages.com", "reuters.com",
            "flickr.com", "wikipedia.org",
        }
        for domain in essential:
            assert domain in TRUSTED_DOMAINS, f"'{domain}' deveria estar em TRUSTED_DOMAINS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
