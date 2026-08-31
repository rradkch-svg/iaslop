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

def main():
    print("=" * 70)
    print("🍪 EXTRATOR AUTOMÁTICO DE COOKIES DO YOUTUBE")
    print("=" * 70)
    print("\n[*] Tentando extrair cookies de sessão do YouTube dos navegadores...")

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
                        print(f"  ✅ Cookies extraídos via browser_cookie3 ({b_name})!")
                        break
                except Exception:
                    pass
        except ImportError:
            pass

    if extracted_cookies:
        # Grava no formato Netscape HTTP Cookie File reconhecido pelo yt-dlp e curl
        with open(OUTPUT_COOKIES, "w", encoding="utf-8") as f:
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

        print(f"\n🎉 SUCESSO! Arquivo gravado em: {OUTPUT_COOKIES} ({os.path.getsize(OUTPUT_COOKIES)} bytes)")
        print("💡 O yt-dlp agora usará esses cookies automaticamente em todos os downloads!")
    else:
        print("\n⚠️ Nenhum cookie de sessão do YouTube pôde ser extraído automaticamente.")
        print("DICA: Para extrair manualmente com 1 clique:")
        print("1. Instale a extensão 'Get cookies.txt LOCALLY' no seu Chrome/Edge/Firefox.")
        print("2. Acesse https://www.youtube.com logado em sua conta.")
        print(f"3. Exporte e salve o arquivo como: '{OUTPUT_COOKIES}'")

if __name__ == "__main__":
    main()
