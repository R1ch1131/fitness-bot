/** Keep custom artwork small enough to travel with the existing cloud backup. */
export async function prepareCover(file: File): Promise<string> {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Выбери картинку JPG, PNG или WebP.');
  if (file.size > 10 * 1024 * 1024) throw new Error('Выбери картинку размером до 10 МБ.');
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const scale = Math.min(1, 720 / image.naturalWidth, 400 / image.naturalHeight);
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Не удалось подготовить картинку.');
    context.fillStyle = '#142324';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const data = canvas.toDataURL('image/webp', 0.82);
    return data.startsWith('data:image/webp') ? data : canvas.toDataURL('image/jpeg', 0.7);
  } catch (error) {
    throw new Error(error instanceof Error && error.message.startsWith('Не удалось') ? error.message : 'Не удалось прочитать картинку. Попробуй другой файл.');
  } finally { URL.revokeObjectURL(url); }
}
