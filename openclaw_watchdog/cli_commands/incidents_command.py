from __future__ import annotations


def _print_not_found(*, args, json_printer) -> int:
    if getattr(args, 'json', False):
        json_printer({'error': 'incident-not-found', 'incident_id': args.incident_id})
    else:
        print(f'incident_not_found={args.incident_id}')
    return 1


def run(
    *,
    args,
    engine,
    incident_ops,
    json_printer,
    incidents_list_printer,
    incident_detail_printer,
    incident_queue_printer,
    incident_timeline_printer,
) -> int:
    if args.incidents_command == 'list':
        ack_arg = getattr(args, 'ack', 'all')
        acknowledged = None if ack_arg == 'all' else ack_arg == 'yes'
        notes_arg = getattr(args, 'notes', 'all')
        has_notes = None if notes_arg == 'all' else notes_arg == 'yes'
        payload = {
            'state_filter': getattr(args, 'state', 'all'),
            'owner_filter': getattr(args, 'owner', ''),
            'ack_filter': ack_arg,
            'notes_filter': notes_arg,
            'attention_filter': getattr(args, 'attention', 'all'),
            'incidents': incident_ops.list_incident_snapshots(
                engine,
                limit=max(1, getattr(args, 'limit', 10)),
                state=getattr(args, 'state', 'all'),
                owner=getattr(args, 'owner', ''),
                acknowledged=acknowledged,
                has_notes=has_notes,
                attention_needed=None if getattr(args, 'attention', 'all') == 'all' else getattr(args, 'attention', 'all') == 'yes',
            ),
        }
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            incidents_list_printer(payload)
        return 0

    if args.incidents_command == 'show':
        payload = incident_ops.incident_detail_payload(engine, args.incident_id)
        if not payload:
            return _print_not_found(args=args, json_printer=json_printer)
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            incident_detail_printer(payload, notes_all=getattr(args, 'notes_all', False))
        return 0

    if args.incidents_command == 'queue':
        payload = incident_ops.incident_queue_payload(engine, limit=max(1, getattr(args, 'limit', 10)))
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            incident_queue_printer(payload)
        return 0

    if args.incidents_command == 'timeline':
        limit = getattr(args, 'limit', 0)
        payload = incident_ops.incident_timeline_payload(engine, args.incident_id, limit=limit if limit > 0 else None)
        if not payload:
            return _print_not_found(args=args, json_printer=json_printer)
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            incident_timeline_printer(payload)
        return 0

    if args.incidents_command == 'assign':
        payload = incident_ops.set_incident_owner(engine, args.incident_id, args.owner)
    elif args.incidents_command == 'unassign':
        payload = incident_ops.clear_incident_owner(engine, args.incident_id)
    elif args.incidents_command == 'ack':
        payload = incident_ops.acknowledge_incident(engine, args.incident_id, acknowledged_by=args.by, note=args.note)
    elif args.incidents_command == 'unack':
        payload = incident_ops.clear_incident_acknowledgement(engine, args.incident_id)
    elif args.incidents_command == 'note':
        payload = incident_ops.add_incident_note(engine, args.incident_id, note_by=args.by, message=args.message)
    else:
        payload = incident_ops.current_incident_payload(engine)
        if not payload:
            if getattr(args, 'json', False):
                json_printer({})
            else:
                print('incident=none')
            return 0
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            incident_detail_printer(payload)
        return 0

    if not payload:
        return _print_not_found(args=args, json_printer=json_printer)
    if getattr(args, 'json', False):
        json_printer(payload)
    else:
        incident_detail_printer(payload)
    return 0
