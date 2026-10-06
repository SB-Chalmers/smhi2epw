#!/usr/bin/env bash
# Install the checksum-pinned study engine on Ubuntu 24.04 x86_64.
set -euo pipefail

eplus_build="24.2.0-94a887817b"
eplus_archive="EnergyPlus-${eplus_build}-Linux-Ubuntu24.04-x86_64.tar.gz"
eplus_sha256="af523c74226659c21002a8a2d4cb1789189d4aeea8194d4800f8f7a8fac9adcd"
eplus_url="https://github.com/NatLabRockies/EnergyPlus/releases/download/v24.2.0a/${eplus_archive}"
eplus_install_dir="${1:?Usage: bash scripts/install_energyplus.sh INSTALL_DIRECTORY}"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "This installer requires Linux x86_64; use the official platform archive locally." >&2
    exit 1
fi

if [[ ! -x "${eplus_install_dir}/energyplus" ]]; then
    eplus_temp_dir="$(mktemp -d)"
    trap 'rm -rf "$eplus_temp_dir"' EXIT
    curl --fail --location --retry 3 --connect-timeout 30 \
        "$eplus_url" --output "${eplus_temp_dir}/${eplus_archive}"
    printf '%s  %s\n' "$eplus_sha256" "${eplus_temp_dir}/${eplus_archive}" | sha256sum --check --strict
    mkdir "${eplus_temp_dir}/extracted"
    tar -xzf "${eplus_temp_dir}/${eplus_archive}" -C "${eplus_temp_dir}/extracted"
    eplus_source_dir=""
    for eplus_candidate in "${eplus_temp_dir}/extracted/energyplus" "${eplus_temp_dir}/extracted"/*/energyplus; do
        if [[ -x "$eplus_candidate" ]]; then
            if [[ -n "$eplus_source_dir" ]]; then
                echo "Multiple EnergyPlus executables found in the pinned archive." >&2
                exit 1
            fi
            eplus_source_dir="$(dirname "$eplus_candidate")"
        fi
    done
    if [[ -z "$eplus_source_dir" ]]; then
        echo "The pinned archive has no EnergyPlus executable." >&2
        exit 1
    fi
    mkdir -p "$eplus_install_dir"
    cp -a "${eplus_source_dir}/." "$eplus_install_dir/"
fi

eplus_engine_version="$("${eplus_install_dir}/energyplus" --version)"
if [[ "$eplus_engine_version" != *"$eplus_build"* ]]; then
    echo "Wrong EnergyPlus build: $eplus_engine_version; expected $eplus_build." >&2
    exit 1
fi
printf '%s\n' "$eplus_engine_version"
if [[ -n "${GITHUB_ENV:-}" ]]; then
    printf 'ENERGYPLUS_EXE=%s/energyplus\n' "$eplus_install_dir" >> "$GITHUB_ENV"
fi
