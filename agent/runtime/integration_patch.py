"""Patch only reviewed routing entry points; retain all company source privately."""
import ast

def once(source,old,new):
    if source.count(old)!=1:raise ValueError('Integration anchor changed; review required')
    result=source.replace(old,new,1);ast.parse(result);return result

def patch_workspace(source):
    source=once(source,"def enqueue(owner, data):\n", "def enqueue(owner, data):\n    import runtime_gateway as crypto_runtime_gateway\n    if crypto_runtime_gateway.selected(data.get('session'), data.get('question')) is not None:\n        return crypto_runtime_gateway.enqueue(owner, data)\n")
    source=once(source,"                    return self.send(200, [dict(r) for r in rows])", "                    import runtime_gateway as crypto_runtime_gateway\n                    return self.send(200, crypto_runtime_gateway.merged(owner, [dict(r) for r in rows], session))")
    source=once(source,"            if m:\n                with connect() as c:\n                    changed = c.execute(\"UPDATE jobs SET status='cancelled'", "            if m:\n                import runtime_gateway as crypto_runtime_gateway\n                crypto_result = crypto_runtime_gateway.call('cancel', owner=owner, id=m[1])\n                if crypto_result is not None:\n                    return self.send(200 if crypto_result['ok'] else 409, crypto_result)\n                with connect() as c:\n                    changed = c.execute(\"UPDATE jobs SET status='cancelled'")
    # Keep company cancellation available when crypto runtime is down.
    source=once(source,"                crypto_result = crypto_runtime_gateway.call('cancel', owner=owner, id=m[1])", "                try:\n                    crypto_result = crypto_runtime_gateway.call('cancel', owner=owner, id=m[1])\n                except (OSError, ValueError):\n                    crypto_result = None")
    return source

def patch_helper(source):
    source=once(source,"                    import server\n                    if data['op']=='agent_submit': result=server.enqueue(2,data['request'])", "                    import runtime_gateway as crypto_runtime_gateway\n                    if data['op']=='agent_submit' and crypto_runtime_gateway.selected(data['request'].get('session'),data['request'].get('question')) is not None:\n                        result=crypto_runtime_gateway.enqueue(2,data['request'])\n                    elif data['op']=='agent_submit':\n                        import server\n                        result=server.enqueue(2,data['request'])")
    source=once(source,"                    elif data['op']=='agent_jobs':\n                        with server.connect() as c:result=[dict(r) for r in c.execute('SELECT * FROM jobs WHERE owner=2 ORDER BY created DESC LIMIT 20')]", "                    elif data['op']=='agent_jobs':\n                        import server\n                        with server.connect() as c:result=[dict(r) for r in c.execute('SELECT * FROM jobs WHERE owner=2 ORDER BY created DESC LIMIT 20')]\n                        result=crypto_runtime_gateway.merged(2,result,limit=20)")
    return source

def patch_main(source):
    if '    from crypto_boundary import maybe_run\n' not in source:
        # A reviewed concurrent company update may have replaced the old boundary.
        # Reinstall the same public company-context boundary before changing transport.
        from crypto_boundary import patch
        source=patch(source)
    return once(source,'    from crypto_boundary import maybe_run\n','    from runtime_gateway import maybe_run\n')
