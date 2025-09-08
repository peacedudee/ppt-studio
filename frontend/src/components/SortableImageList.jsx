import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { arrayMove, SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { SimpleGrid, Card, Image, Center, Text, ActionIcon } from '@mantine/core';
import { IconX, IconGripVertical } from '@tabler/icons-react';
import { useMemo, useEffect } from 'react';

function SortableItem({ file, id, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    position: 'relative',
    cursor: isDragging ? 'grabbing' : 'default',
    opacity: isDragging ? 0.9 : 1,
  };

  const url = useMemo(() => URL.createObjectURL(file), [file]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);

  return (
    <div ref={setNodeRef} style={style}>
      {/* 1) DELETE: block drag in CAPTURE phase + preventDefault */}
      <ActionIcon
        variant="filled"
        color="red"
        size="xs"
        radius="xl"
        component="button"
        type="button"
        onPointerDownCapture={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onMouseDownCapture={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onTouchStartCapture={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onDelete(id);
        }}
        style={{ position: 'absolute', top: -5, right: -5, zIndex: 10, cursor: 'pointer' }}
        draggable={false}
        data-no-dnd
      >
        <IconX size={12} />
      </ActionIcon>

      {/* 2) DRAG HANDLE: listeners ONLY here (no stopPropagation here) */}
      <div
        {...attributes}
        {...listeners}
        style={{
          position: 'absolute',
          left: -6,
          top: -6,
          padding: 6,
          cursor: 'grab',
          zIndex: 5,
          userSelect: 'none',
          touchAction: 'none', // helps pointer handling on touch
        }}
      >
        <IconGripVertical size={14} />
      </div>

      <Card withBorder padding="xs">
        <Center>
          <Image src={url} w={80} h={60} fit="contain" draggable={false} />
        </Center>
        <Text size="xs" truncate ta="center" mt={5}>
          {file.name}
        </Text>
      </Card>
    </div>
  );
}

export default function SortableImageList({ files, setFiles }) {
  // 3) Add an activation distance to reduce accidental drags
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const handleDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    setFiles((current) => {
      const oldIndex = current.findIndex((f) => f.name === active.id);
      const newIndex = current.findIndex((f) => f.name === over.id);
      if (oldIndex === -1 || newIndex === -1) return current;
      return arrayMove(current, oldIndex, newIndex);
    });
  };

  const handleDelete = (fileName) => {
    setFiles((current) => current.filter((f) => f.name !== fileName));
  };

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={files.map((f) => f.name)} strategy={rectSortingStrategy}>
        <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} mt="md">
          {files.map((file) => (
            <SortableItem key={file.name} id={file.name} file={file} onDelete={handleDelete} />
          ))}
        </SimpleGrid>
      </SortableContext>
    </DndContext>
  );
}