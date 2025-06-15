# WebDAV Production Configuration Example

This document shows how to properly configure WebDAV user management for production environments.

## Production vs Testing Configuration

### Testing (Performance Optimized)
```python
# For tests - skips Apache reload for speed
apache_sync = ApacheServiceSynchronizer(
    config_manager,
    apache_container_manager,
    skip_reload=True  # Skip reload for test performance
)
```

### Production (Proper Behavior)
```python
# For production - includes Apache reload (required)
apache_sync = ApacheServiceSynchronizer(
    config_manager,
    apache_container_manager,
    skip_reload=False  # Enable reload for production (default)
)
```

## Why Apache Reload is Required

Apache HTTP server with `mod_auth_digest` does **not** automatically detect changes to htdigest authentication files. The authentication file is read when:

1. Apache starts up
2. Configuration is reloaded (`apache2ctl graceful`)
3. Apache is restarted

## Performance Considerations

### Production
- **User additions/modifications**: Require `apache2ctl graceful` (~2-3 seconds)
- **Authentication requests**: Fast (file-based lookup)
- **Best practice**: Batch user operations when possible

### Testing
- **User operations**: Skip reload for 3x faster tests
- **Authentication**: Still works because containers are frequently restarted
- **Trade-off**: Test speed vs production fidelity

## Configuration Management

The project automatically handles this through:

1. **Configuration watcher** monitors YAML config changes
2. **Synchronization system** updates htdigest files
3. **Apache graceful reload** picks up authentication changes
4. **Environment-aware handling** (testing vs production)

## Security Notes

- WebDAV uses digest authentication (more secure than basic auth)
- HTTPS-only configuration prevents credential interception
- Apache reload doesn't interrupt active connections (graceful)
