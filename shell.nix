{ pkgs ? import <nixpkgs> {} }:

let
  flake = import ./flake.nix;
  system = pkgs.stdenv.hostPlatform.system;
  flakeUtils = {
    lib.eachDefaultSystem = f: {
      devShells.${system} = (f system).devShells;
      apps.${system} = (f system).apps;
    };
  };
  outputs = flake.outputs {
    self = ./.;
    nixpkgs = pkgs.path;
    flake-utils = flakeUtils;
  };
in
outputs.devShells.${system}.default
