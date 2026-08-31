"""
Script utilitário para exportar cookies do YouTube dos navegadores instalados no Windows
(Microsoft Edge, Google Chrome, Brave, Mozilla Firefox) diretamente para o arquivo 'cookies.txt'.
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_COOKIES = os.path.join(PROJECT_ROOT, "cookies.txt")

def export_youtube_cookies(output_file: str = None, verbose: bool = False) -> str:
    """Extrai cookies dos navegadores suportados e salva no formato Netscape."""
    target_path = output_file or OUTPUT_COOKIES
    extracted_cookies = []

    # 1. Tentativa via rookiepy (suporte a Edge, Chrome, Brave, Firefox)
    try:
        import rookiepy
        browsers = [
            ("Microsoft Edge", rookiepy.edge),
            ("Google Chrome", rookiepy.chrome),
            ("Brave Browser", rookiepy.brave),
            ("Mozilla Firefox", rookiepy.firefox),
            ("Opera", rookiepy.opera)
        ]
        for name, getter in browsers:
            try:
                c = getter(domains=[".youtube.com", "youtube.com", ".google.com"])
                if c:
                    if verbose:
                        print(f"  ✅ {len(c)} cookies encontrados no {name}!")
                    extracted_cookies.extend(c)
            except Exception:
                pass
    except ImportError:
        pass

    # 2. Tentativa complementar via browser_cookie3
    if not extracted_cookies:
        try:
            import browser_cookie3
            for b_name, b_fn in [("Edge", browser_cookie3.edge), ("Chrome", browser_cookie3.chrome), ("Firefox", browser_cookie3.firefox)]:
                try:
                    cj = b_fn(domain_name=".youtube.com")
                    for c in cj:
                        extracted_cookies.append({
                            "domain": c.domain,
                            "path": c.path,
                            "secure": c.secure,
                            "expires": c.expires,
                            "name": c.name,
                            "value": c.value
                        })
                    if extracted_cookies:
                        if verbose:
                            print(f"  ✅ Cookies extraídos via browser_cookie3 ({b_name})!")
                        break
                except Exception:
                    pass
        except ImportError:
            pass

    if extracted_cookies:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# Gerado automaticamente pelo Minuto Inexplicável Studio\n")
            f.write("# Permite downloads do YouTube sem bloqueios de bot / rate limits\n\n")
            seen_keys = set()
            for cookie in extracted_cookies:
                domain = cookie.get("domain", "")
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                path = cookie.get("path", "/")
                secure = "TRUE" if cookie.get("secure") else "FALSE"
                expires = str(cookie.get("expires", 0) or 0)
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                key = (domain, path, name)
                if key not in seen_keys and name and value:
                    seen_keys.add(key)
                    f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        return target_path
    return None

def main():
    print("=" * 70)
    print("🍪 EXTRATOR AUTOMÁTICO DE COOKIES DO YOUTUBE")
    print("=" * 70)
    print("\n[*] Tentando extrair cookies de sessão do YouTube dos navegadores...")

    result = export_youtube_cookies(OUTPUT_COOKIES, verbose=True)
    if result and os.path.exists(result):
        print(f"\n🎉 SUCESSO! Arquivo gravado em: {result} ({os.path.getsize(result)} bytes)")
        print("💡 O yt-dlp agora usará esses cookies automaticamente em todos os downloads!")
    else:
        print("\n⚠️ Nenhum cookie de sessão do YouTube pôde ser extraído automaticamente.")
        print("DICA: Para extrair manualmente com 1 clique:")
        print("1. Instale a extensão 'Get cookies.txt LOCALLY' no seu Chrome/Edge/Firefox.")
        print("2. Acesse https://www.youtube.com logado em sua conta.")
        print(f"3. Exporte e salve o arquivo como: '{OUTPUT_COOKIES}'")

if __name__ == "__main__":
    main()
