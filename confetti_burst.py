"""Bottom-origin confetti bursts for receipts and the visual test page."""

from __future__ import annotations

import json

import streamlit.components.v1 as components


VARIANTS = {
    "garden": "Garden burst",
    "twin": "Twin fountain",
    "starlight": "Starlight",
    "petals": "Soft petals",
}


def render_confetti_burst(
    variant: str = "garden",
    *,
    height: int = 520,
    seed: str = "receipt",
) -> None:
    """Render a ballistic burst: launch upward from the bottom, then fall."""

    selected = variant if variant in VARIANTS else "garden"
    components.html(
        f"""
        <style>
          html,body{{margin:0;overflow:hidden;background:transparent}}
          canvas{{display:block;width:100%;height:100%}}
        </style>
        <canvas id="burst" aria-label="Celebratory confetti"></canvas>
        <script>
        (() => {{
          const canvas = document.getElementById('burst');
          const ctx = canvas.getContext('2d');
          const variant = {json.dumps(selected)};
          const seedText = {json.dumps(seed)};
          let width=0,height=0,dpr=1,frame=0;
          function resize(){{
            dpr=Math.min(window.devicePixelRatio||1,2);
            width=canvas.clientWidth; height=canvas.clientHeight;
            canvas.width=width*dpr; canvas.height=height*dpr;
            ctx.setTransform(dpr,0,0,dpr,0,0);
          }}
          resize(); window.addEventListener('resize',resize);
          let state=[...seedText].reduce((n,c)=>(n*31+c.charCodeAt(0))>>>0,2166136261);
          const random=()=>{{state=(1664525*state+1013904223)>>>0;return state/4294967296}};
          const palettes={{
            garden:['#d7ff48','#7bdcb5','#a993ff','#ff8066','#12211b'],
            twin:['#5536c8','#d7ff48','#ff8066','#f4efe4','#14241d'],
            starlight:['#f8dc68','#fff8d6','#a993ff','#6fddff','#26334a'],
            petals:['#ff8ea1','#ffc2cc','#f5d6ff','#b9ead7','#fff4e6']
          }};
          const settings={{
            garden:{{count:88,speed:12,spread:0.95,gravity:.19,drag:.992,shape:'paper'}},
            twin:{{count:104,speed:13.5,spread:.55,gravity:.205,drag:.993,shape:'paper'}},
            starlight:{{count:62,speed:11.5,spread:.82,gravity:.16,drag:.994,shape:'star'}},
            petals:{{count:72,speed:10.5,spread:.72,gravity:.13,drag:.991,shape:'petal'}}
          }};
          const s=settings[variant], colors=palettes[variant];
          const particles=Array.from({{length:s.count}},(_,i)=>{{
            const twin=variant==='twin';
            const side=i%2===0?-1:1;
            const origin=twin ? width*(side<0?.28:.72) : width*(.42+random()*.16);
            const angle=(twin ? side*(.18+random()*.34) : (random()-.5)*s.spread);
            const speed=s.speed*(.72+random()*.5);
            return {{x:origin,y:height+8,vx:Math.sin(angle)*speed+(random()-.5)*1.2,
              vy:-Math.cos(angle)*speed,rotation:random()*6.28,spin:(random()-.5)*.32,
              size:5+random()*7,color:colors[i%colors.length],life:0,delay:random()*16}};
          }});
          function star(x,y,r,rotation){{
            ctx.beginPath();
            for(let i=0;i<10;i++){{const radius=i%2?r*.42:r;const a=rotation+i*Math.PI/5;
              ctx.lineTo(x+Math.cos(a)*radius,y+Math.sin(a)*radius)}}ctx.closePath();ctx.fill();
          }}
          function draw(p){{
            ctx.save();ctx.translate(p.x,p.y);ctx.rotate(p.rotation);ctx.fillStyle=p.color;
            if(s.shape==='star') star(0,0,p.size*.7,0);
            else if(s.shape==='petal'){{ctx.beginPath();ctx.ellipse(0,0,p.size*.72,p.size*.38,0,0,6.29);ctx.fill()}}
            else ctx.fillRect(-p.size/2,-p.size*.72,p.size,p.size*1.44);
            ctx.restore();
          }}
          function animate(){{
            ctx.clearRect(0,0,width,height); let active=false;
            particles.forEach(p=>{{
              if(p.delay-->0){{active=true;return}}
              p.life++;p.vy+=s.gravity;p.vx*=s.drag;p.x+=p.vx;p.y+=p.vy;
              p.rotation+=p.spin;p.spin*=.998;
              if(p.y<height+30 && p.life<430){{draw(p);active=true}}
            }});
            frame++; if(active && frame<460) requestAnimationFrame(animate);
          }}
          requestAnimationFrame(animate);
        }})();
        </script>
        """,
        height=height,
    )
