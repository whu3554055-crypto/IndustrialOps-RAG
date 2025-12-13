#!/bin/sh
# Enable WSL2 GPU via CDI inside a k3d k3s node; restart containerd only (not the whole node).
set -e

GPU_UUID=$(nvidia-smi --query-gpu=uuid --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
LIBDXCORE=$(find /usr/lib -name 'libdxcore.so' 2>/dev/null | head -1)
LIBDXCORE=${LIBDXCORE:-/usr/lib/x86_64-linux-gnu/libdxcore.so}

mkdir -p /var/run/cdi /etc/cdi
nvidia-ctk cdi generate --output=/var/run/cdi/nvidia.yaml

awk -v uuid="$GPU_UUID" -v libdxcore="$LIBDXCORE" '
  /- path: \/dev\/dxg/ && !uuid_added {
    print
    if (uuid != "") {
      print " - name: " uuid
      print "   containerEdits:"
      print "     deviceNodes:"
      print "     - path: /dev/dxg"
    }
    uuid_added = 1
    next
  }
  /- --folder/ && !folder_added {
    print
    dir = libdxcore
    sub(/\/[^\/]*$/, "", dir)
    print " - --folder"
    print " - " dir
    folder_added = 1
    next
  }
  { print }
  END {
    print " - hostPath: " libdxcore
    print "   containerPath: " libdxcore
    print "   options:"
    print "   - ro"
    print "   - nosuid"
    print "   - nodev"
    print "   - rbind"
    print "   - rprivate"
  }
' /var/run/cdi/nvidia.yaml > /tmp/nvidia-patched.yaml
mv /tmp/nvidia-patched.yaml /var/run/cdi/nvidia.yaml
cp /var/run/cdi/nvidia.yaml /etc/cdi/nvidia.yaml

if [ -f /etc/nvidia-container-runtime/config.toml ]; then
  sed -i 's/mode = "auto"/mode = "cdi"/' /etc/nvidia-container-runtime/config.toml || true
  sed -i 's/mode = "legacy"/mode = "cdi"/' /etc/nvidia-container-runtime/config.toml || true
fi

mkdir -p /var/lib/rancher/k3s/agent/etc/containerd
if ! grep -q 'enable_cdi' /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl 2>/dev/null; then
  printf '\n[plugins."io.containerd.grpc.v1.cri"]\n  enable_cdi = true\n' \
    >> /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
fi

CPID=$(pgrep -f 'containerd -c /var/lib/rancher' 2>/dev/null | head -1)
if [ -n "$CPID" ]; then
  kill "$CPID" 2>/dev/null || true
fi

echo "CDI ok uuid=${GPU_UUID:-none}"
