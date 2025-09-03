{
  description = "Kivra Sync - Nix flake to build and develop the project";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }: let
    systems = [ "x86_64-linux" "aarch64-linux" ];
    forAllSystems = f: builtins.listToAttrs (map (system: {
      name = system;
      value = f system;
    }) systems);
  in {
    packages = forAllSystems (system: let
      pkgs = import nixpkgs { inherit system; }; 
      lib = pkgs.lib;
      py = pkgs.python3;
      pyPkgs = pkgs.python3Packages;
    in {
      default = pyPkgs.buildPythonApplication {
        pname = "kivra-sync";
        version = self.rev or "dev";
        src = ./.;

        format = "other"; # custom installPhase, no setuptools/poetry
        dontUseSetuptools = true;

        propagatedBuildInputs = with pyPkgs; [
          pillow
          qrcode
          requests
          weasyprint
        ];

        # System libraries required by WeasyPrint/Pango/Cairo at runtime
        buildInputs = with pkgs; [
          cairo
          pango
          harfbuzz
          freetype
          fontconfig
          gdk-pixbuf
          libxml2
          libxslt
          glib
          fribidi
        ];

        nativeBuildInputs = [ pkgs.makeWrapper ];

        installPhase = ''
          runHook preInstall

          site="${py.sitePackages}"
          mkdir -p "$out/$site" "$out/bin"

          # Install python modules
          cp -r kivra interaction storage utils "$out/$site/"
          cp __version__.py "$out/$site/"
          cp kivra_sync.py "$out/$site/kivra_sync.py"

          # Entry point
          cat > "$out/bin/kivra-sync" << 'EOF'
          #!${py.interpreter}
          import sys
          from kivra_sync import main
          if __name__ == "__main__":
              sys.exit(main())
          EOF
          chmod +x "$out/bin/kivra-sync"

          runHook postInstall
        '';

        # Ensure CFFI can dlopen pango/cairo and friends at runtime
        postFixup = let
          libPath = lib.makeLibraryPath [
            pkgs.pango
            pkgs.cairo
            pkgs.gdk-pixbuf
            pkgs.harfbuzz
            pkgs.freetype
            pkgs.fontconfig
            pkgs.fribidi
            pkgs.glib
            pkgs.libxml2
            pkgs.libxslt
          ];
        in ''
          wrapProgram "$out/bin/kivra-sync" \
            --prefix LD_LIBRARY_PATH : ${lib.escapeShellArg libPath}
        '';

        meta = with lib; {
          description = "Automation tool to sync documents from Kivra";
          homepage = "https://github.com/";
          license = licenses.mit;
          platforms = platforms.linux;
          mainProgram = "kivra-sync";
        };
      };
    });

    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/kivra-sync";
      };
    });

    devShells = forAllSystems (system: let
      pkgs = import nixpkgs { inherit system; };
      pyEnv = pkgs.python3.withPackages (ps: with ps; [
        pillow qrcode requests weasyprint
      ]);
    in {
      default = pkgs.mkShell {
        packages = [
          pyEnv
          # Useful system libs for WeasyPrint during development
          pkgs.cairo pkgs.pango pkgs.harfbuzz pkgs.freetype pkgs.fontconfig pkgs.gdk-pixbuf
          pkgs.libxml2 pkgs.libxslt pkgs.glib pkgs.fribidi
          # Optional: node for release tooling in package.json
          pkgs.nodejs
        ];
      };
    });
  };
}

