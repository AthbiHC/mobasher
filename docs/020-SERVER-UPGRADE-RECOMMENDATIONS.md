# Server Upgrade Recommendations

## Current System Analysis

**Hardware Specifications:**
- CPU: Intel Xeon Gold 6248 @ 2.50GHz (2 cores)
- RAM: 16GB (13GB available)
- Storage: 48GB SSD (29GB free)
- GPU: Virtio GPU (CPU-only processing)
- Load: 3.5 average (overloaded)

**Current Bottlenecks:**
- FFmpeg Video: 132% CPU usage (1.3 cores) - PRIMARY BOTTLENECK
- Only 2 cores total with high system load
- ASR processing not possible due to CPU constraints
- System running at capacity limits

## DigitalOcean Upgrade Recommendations

### 🧪 Staging Environment
**Recommended: CPU-Optimized 4 vCPUs, 8GB RAM - $84/mo**

**Benefits:**
- 100% more CPU power (2→4 vCPUs)
- Enables 1-2 ASR workers
- Smooth video recording (no more CPU spikes)
- $15/mo cost savings vs current setup
- Perfect for development and testing

**Expected Performance:**
- Single channel recording: Stable
- ASR processing: 2-3 segments/minute
- Archive recorder: Reliable operation
- System headroom: ~25% CPU available

### 🏭 Production Environment  
**Recommended: CPU-Optimized 8 vCPUs, 16GB RAM - $168/mo**

**Capacity Planning:**
- Per channel: ~1.6 vCPUs (FFmpeg video + audio + archive)
- 4 channels: 6.4 vCPUs (80% utilization) ✅ Optimal
- 5 channels: 8.0 vCPUs (100% utilization) ⚠️ Maximum
- ASR workers: 2-3 workers possible
- Future scaling: Can handle 4-5 channels reliably

**Alternative for Heavy Load:**
**CPU-Optimized 16 vCPUs, 32GB RAM - $336/mo**
- 6+ channels: Full capacity
- ASR workers: 4-6 workers
- Future-proof for expansion

## Resource Usage Projections

### Single Channel (Current)
```
FFmpeg Video: 1.3 vCPUs
FFmpeg Audio: 0.2 vCPUs  
Archive Recorder: 0.1 vCPUs
Total per channel: 1.6 vCPUs
```

### Multi-Channel Production (6 Channels)
```
Recording: 6 × 1.6 = 9.6 vCPUs
ASR Workers: 2-3 workers = 3 vCPUs
API/DB/System: 1 vCPU
Total Required: 13-14 vCPUs
```

## ASR Performance Optimization

### Staging Configuration
```bash
export ASR_MODEL=medium          # Best balance: speed vs quality
export ASR_DEVICE=cpu           # No GPU available  
export ASR_BEAM=3               # Reduce beam size for speed
export ASR_VAD=1                # Keep VAD enabled
export ASR_WORKERS=1            # Single worker for testing
```

### Production Configuration
```bash
export ASR_MODEL=medium          # Production quality
export ASR_DEVICE=cpu           
export ASR_BEAM=3               
export ASR_VAD=1                
export ASR_WORKERS=2-3          # Multiple workers for throughput
```

## Migration Strategy

### Phase 1: Staging Upgrade
1. Upgrade to 4 vCPU CPU-Optimized ($84/mo)
2. Test ASR workers with medium model
3. Validate archive recorder performance
4. Optimize configurations for production

### Phase 2: Production Deployment
1. Deploy 8 vCPU CPU-Optimized for production ($168/mo)
2. Start with 4 channels (80% CPU utilization)
3. Monitor performance and queue processing
4. Scale to 5-6 channels based on performance

## Cost Analysis

| Environment | vCPUs | RAM | Channels | ASR Workers | Cost/mo | Use Case |
|-------------|-------|-----|----------|-------------|---------|----------|
| Current | 2 | 16GB | 1 | 0 | $99 | ❌ Overloaded |
| Staging | 4 | 8GB | 1-2 | 1-2 | $84 | ✅ Development |
| Production | 8 | 16GB | 4-5 | 2-3 | $168 | ✅ Production |
| Enterprise | 16 | 32GB | 6+ | 4-6 | $336 | 🚀 Heavy Load |

## Key Recommendations

1. **CPU-Optimized over Memory-Optimized**: Better for FFmpeg + ASR workloads
2. **Start Conservative**: Begin with 4 channels, scale up gradually  
3. **Monitor CPU Usage**: Keep below 85% for stability
4. **ASR Model Selection**: Use 'medium' for best speed/quality balance
5. **Gradual Scaling**: Add channels one at a time, monitor performance

## Implementation Notes

- Current 2 vCPU system cannot handle ASR processing
- 4 vCPU upgrade enables development and testing
- 8 vCPU system supports 4-5 production channels
- 16 vCPU system needed for 6+ channels with heavy ASR processing
- Memory requirements are modest (8GB sufficient for staging)
